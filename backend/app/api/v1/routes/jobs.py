import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permissions
from app.core.responses import Pagination, ok
from app.models import Job, JobLog, JobStatus, User
from app.schemas.jobs import JobCreate, JobLogOut, JobOut
from app.services import jobs as job_service
from app.services.audit import record_audit

router = APIRouter(prefix="/jobs", tags=["jobs"])

Reader = Annotated[User, Depends(require_permissions("jobs:read"))]
Writer = Annotated[User, Depends(require_permissions("jobs:write"))]
Canceller = Annotated[User, Depends(require_permissions("jobs:cancel"))]


def _out(job: Job) -> dict:
    return JobOut.model_validate(job).model_dump(mode="json")


@router.get("/types", summary="Allowlisted job types")
async def job_types(_: Reader) -> dict:
    return ok([{"job_type": k, "timeout_seconds": v.timeout_seconds, "max_retries": v.max_retries,
                "cancellable": v.cancellable} for k, v in job_service.JOB_DEFINITIONS.items()])


@router.get("/stats", summary="Job counts by status")
async def stats(_: Reader, db: DbSession) -> dict:
    return ok((await job_service.job_stats(db)).model_dump())


@router.get("", summary="List jobs")
async def list_jobs(_: Reader, db: DbSession, page: Annotated[Pagination, Depends()],
                    status: Annotated[JobStatus | None, Query()] = None,
                    job_type: Annotated[str | None, Query(max_length=100)] = None) -> dict:
    query = select(Job)
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    jobs = (await db.execute(query.order_by(Job.created_at.desc()).offset(page.offset).limit(page.page_size))).scalars()
    return ok([_out(j) for j in jobs], page.meta(total).model_dump())


@router.post("", status_code=201, summary="Create and enqueue a job")
async def create_job(body: Annotated[JobCreate, Body()], request: Request, user: Writer, db: DbSession) -> dict:
    job = await job_service.create_job(db, body.job_type, body.params.model_dump(), user)
    await record_audit(db, "jobs.create", request=request, user=user, resource_type="job", resource_id=str(job.id),
                       details={"job_type": job.job_type})
    return ok(_out(job))


@router.get("/{job_id}", summary="Get a job")
async def get_job(job_id: uuid.UUID, _: Reader, db: DbSession) -> dict:
    return ok(_out(await job_service.get_job(db, job_id)))


@router.get("/{job_id}/logs", summary="Get job logs (incremental via after_id)")
async def get_logs(job_id: uuid.UUID, _: Reader, db: DbSession,
                   after_id: Annotated[int, Query(ge=0)] = 0,
                   limit: Annotated[int, Query(ge=1, le=1000)] = 500) -> dict:
    await job_service.get_job(db, job_id)
    logs = (await db.execute(select(JobLog).where(JobLog.job_id == job_id, JobLog.id > after_id)
                             .order_by(JobLog.id).limit(limit))).scalars()
    return ok([JobLogOut.model_validate(entry).model_dump(mode="json") for entry in logs])


@router.post("/{job_id}/retry", summary="Retry a failed or cancelled job")
async def retry(job_id: uuid.UUID, request: Request, user: Writer, db: DbSession) -> dict:
    job = await job_service.retry_job(db, job_id)
    await record_audit(db, "jobs.retry", request=request, user=user, resource_type="job", resource_id=str(job.id))
    return ok(_out(job))


@router.post("/{job_id}/cancel", summary="Cancel a queued job, or request cancellation of a cancellable running job")
async def cancel(job_id: uuid.UUID, request: Request, user: Canceller, db: DbSession) -> dict:
    job = await job_service.cancel_job(db, job_id)
    await record_audit(db, "jobs.cancel", request=request, user=user, resource_type="job", resource_id=str(job.id))
    return ok(_out(job))
