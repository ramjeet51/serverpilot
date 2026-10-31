import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.responses import ApiError
from app.models import Job, JobStatus, User
from app.schemas.jobs import JobOut, JobStats
from app.services.events import publish
from app.worker.celery_app import celery_app


@dataclass(frozen=True)
class JobDefinition:
    timeout_seconds: int
    max_retries: int
    cancellable: bool


# Allowlist of job types the platform will execute. Anything else is rejected at the API boundary.
JOB_DEFINITIONS: dict[str, JobDefinition] = {
    "platform.diagnostics": JobDefinition(timeout_seconds=120, max_retries=2, cancellable=False),
    "platform.sleep_test": JobDefinition(timeout_seconds=360, max_retries=0, cancellable=True),
    # Package and service changes are not cancelled mid-flight: apt and systemctl must finish.
    "software.apply": JobDefinition(timeout_seconds=900, max_retries=0, cancellable=False),
    "services.apply": JobDefinition(timeout_seconds=180, max_retries=0, cancellable=False),
}


def _enqueue(job: Job) -> str:
    # apply_async honours task_always_eager (send_task does not), so tests run the job inline
    # and production still publishes it to the Redis broker.
    from app.worker.tasks import run_job

    result = run_job.apply_async(args=[str(job.id)], soft_time_limit=job.timeout_seconds,
                                 time_limit=job.timeout_seconds + 30)
    return result.id


async def _publish_job(job: Job) -> None:
    await publish("job.updated", JobOut.model_validate(job).model_dump(mode="json"))


async def _commit_and_enqueue(db: AsyncSession, job: Job) -> Job:
    # Commit first so a fast worker can load the row. Only the task id is written afterwards,
    # otherwise this session would overwrite a status the worker already recorded.
    await db.commit()
    job_id = job.id
    try:
        task_id = await run_in_threadpool(_enqueue, job)
    except Exception as exc:
        db.expire_all()
        await db.execute(update(Job).where(Job.id == job_id).values(
            status=JobStatus.failed, error_message="Job queue unavailable", finished_at=datetime.now(UTC)))
        await db.commit()
        raise ApiError(503, "queue_unavailable", "Job queue is unavailable; try again shortly") from exc
    db.expire(job)
    await db.execute(update(Job).where(Job.id == job_id).values(celery_task_id=task_id))
    await db.commit()
    await db.refresh(job)
    await _publish_job(job)
    return job


async def create_job(db: AsyncSession, job_type: str, params: dict, user: User,
                     server_id: uuid.UUID | None = None) -> Job:
    definition = JOB_DEFINITIONS.get(job_type)
    if definition is None:
        raise ApiError(400, "unsupported_job_type", f"Job type '{job_type}' is not allowed")
    timeout = min(definition.timeout_seconds, get_settings().job_max_timeout_seconds)
    job = Job(job_type=job_type, params=params, status=JobStatus.queued, timeout_seconds=timeout,
              max_retries=definition.max_retries, cancellable=definition.cancellable, created_by_id=user.id,
              server_id=server_id)
    db.add(job)
    return await _commit_and_enqueue(db, job)


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise ApiError(404, "not_found", "Job not found")
    return job


async def retry_job(db: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await get_job(db, job_id)
    if job.status not in (JobStatus.failed, JobStatus.cancelled):
        raise ApiError(409, "invalid_state", f"Only failed or cancelled jobs can be retried (current: {job.status.value})")
    job.status = JobStatus.queued
    job.error_message = None
    job.result = None
    job.progress = 0
    job.cancel_requested = False
    job.started_at = None
    job.finished_at = None
    job.queued_at = datetime.now(UTC)
    return await _commit_and_enqueue(db, job)


async def cancel_job(db: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await get_job(db, job_id)
    if job.status.is_terminal:
        raise ApiError(409, "invalid_state", f"Job already finished ({job.status.value})")
    if job.status == JobStatus.queued:
        if job.celery_task_id:
            await run_in_threadpool(celery_app.control.revoke, job.celery_task_id)
        job.status = JobStatus.cancelled
        job.finished_at = datetime.now(UTC)
        job.error_message = "Cancelled before execution"
    elif job.cancellable:
        # Running jobs stop cooperatively at their next checkpoint.
        job.cancel_requested = True
    else:
        raise ApiError(409, "not_cancellable", "This job type cannot be safely cancelled while running")
    await db.commit()
    await db.refresh(job)
    await _publish_job(job)
    return job


async def job_stats(db: AsyncSession) -> JobStats:
    rows = (await db.execute(select(Job.status, func.count()).group_by(Job.status))).all()
    stats = JobStats(**{status.value: count for status, count in rows})
    since = datetime.now(UTC) - timedelta(hours=24)
    stats.failed_last_24h = (await db.execute(
        select(func.count()).select_from(Job).where(Job.status == JobStatus.failed, Job.created_at >= since)
    )).scalar_one()
    return stats
