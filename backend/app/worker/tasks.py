"""Celery job runner. Every job goes through `run_job`, which dispatches to an allowlisted handler."""

import logging
import platform
import shutil
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_sync_sessionmaker
from app.core.redis import get_sync_redis
from app.models import Job, JobLog, JobStatus
from app.schemas.jobs import JobOut
from app.services.events import publish_sync
from app.worker.celery_app import celery_app

logger = logging.getLogger("serverpilot.worker")


class JobCancelled(Exception):
    pass


class JobFailed(Exception):
    def __init__(self, message: str, result: dict | None = None) -> None:
        super().__init__(message)
        self.result = result


class JobContext:
    def __init__(self, session: Session, job: Job) -> None:
        self.session = session
        self.job = job

    def log(self, message: str, level: str = "info", data: dict[str, Any] | None = None) -> None:
        entry = JobLog(job_id=self.job.id, level=level, message=message, data=data)
        self.session.add(entry)
        self.session.commit()
        publish_sync("job.log", {"job_id": str(self.job.id), "id": entry.id, "level": level, "message": message,
                                 "data": data, "created_at": entry.created_at.isoformat()})

    def progress(self, value: int) -> None:
        self.job.progress = max(0, min(100, value))
        self.session.commit()
        _publish_job(self.job)

    def checkpoint(self) -> None:
        self.session.refresh(self.job, attribute_names=["cancel_requested"])
        if self.job.cancel_requested:
            raise JobCancelled()


def _publish_job(job: Job) -> None:
    publish_sync("job.updated", JobOut.model_validate(job).model_dump(mode="json"))


def _diagnostics(ctx: JobContext, _: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    checks: dict[str, Any] = {}

    ctx.log("Checking PostgreSQL connectivity")
    started = time.perf_counter()
    version = ctx.session.execute(text("SHOW server_version")).scalar_one()
    checks["postgres"] = {"ok": True, "version": version, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    ctx.log(f"PostgreSQL {version} reachable", data=checks["postgres"])
    ctx.progress(35)

    ctx.log("Checking Redis connectivity")
    started = time.perf_counter()
    info = get_sync_redis().info("server")
    checks["redis"] = {"ok": True, "version": info.get("redis_version"),
                       "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    ctx.log(f"Redis {info.get('redis_version')} reachable", data=checks["redis"])
    ctx.progress(70)

    ctx.log("Checking log directory disk capacity")
    s.log_path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(s.log_path)
    free_pct = round(usage.free / usage.total * 100, 1)
    checks["disk"] = {"ok": free_pct > 5, "path": str(s.log_path), "free_percent": free_pct}
    ctx.log(f"Log volume has {free_pct}% free", level="info" if free_pct > 5 else "warning", data=checks["disk"])
    ctx.progress(90)

    checks["worker"] = {"ok": True, "hostname": platform.node(), "python": platform.python_version()}
    return {"healthy": all(c["ok"] for c in checks.values()), "checks": checks}


def _sleep_test(ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
    duration = int(params.get("duration_seconds", 10))
    for second in range(1, duration + 1):
        ctx.checkpoint()
        time.sleep(1)
        ctx.log(f"Tick {second}/{duration}")
        ctx.progress(int(second / duration * 100))
    if params.get("fail_at_end"):
        raise RuntimeError("Requested failure (fail_at_end=true)")
    return {"slept_seconds": duration}


def _release_lock(params: dict[str, Any]) -> None:
    owner = params.get("lock_owner")
    server_id = params.get("server_id")
    if isinstance(owner, str) and isinstance(server_id, str):
        from app.services.agent_bus import release_operation_lock
        release_operation_lock(server_id, owner)


def _agent_operation(ctx: JobContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    from app.models import Agent
    from app.services.agent_bus import AgentOffline, AgentTimeout, dispatch_command

    server_id = params.get("server_id")
    args = params.get("args") if isinstance(params.get("args"), dict) else {}
    if not isinstance(server_id, str):
        raise JobFailed("Job is missing its server")
    agent = ctx.session.execute(select(Agent).where(Agent.server_id == uuid.UUID(server_id))).scalar_one_or_none()
    if agent is None:
        raise JobFailed("This server has no agent")
    ctx.progress(15)
    try:
        payload = dispatch_command(str(agent.id), action, args, max(10, ctx.job.timeout_seconds - 15), ctx.log)
    except AgentOffline as exc:
        raise JobFailed("The agent on this server is not connected") from exc
    except AgentTimeout as exc:
        raise JobFailed("The agent did not finish the operation in time") from exc
    if not payload.get("ok"):
        raise JobFailed(str(payload.get("message") or "Operation failed"), {
            "exit_code": payload.get("exit_code"), "error": payload.get("error"),
        })
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    result["exit_code"] = payload.get("exit_code", 0)
    ctx.progress(90)
    return result


def _software_apply(ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
    args = params.get("args") or {}
    ctx.log(f"Package {args.get('action')} {args.get('package') or args.get('software_id')}")
    result = _agent_operation(ctx, params, "software.apply")
    from app.services.host_ops import save_software_sync
    save_software_sync(ctx.session, uuid.UUID(params["server_id"]), [{
        "id": result.get("software_id"),
        "installed": result.get("action") != "remove" and bool(result.get("version")),
        "version": result.get("version"),
        "candidate": result.get("version"),
    }])
    return result


def _services_apply(ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
    args = params.get("args") or {}
    ctx.log(f"Service {args.get('action')} {args.get('unit')}")
    return _agent_operation(ctx, params, "services.apply")


HANDLERS: dict[str, Callable[[JobContext, dict[str, Any]], dict[str, Any]]] = {
    "platform.diagnostics": _diagnostics,
    "platform.sleep_test": _sleep_test,
    "software.apply": _software_apply,
    "services.apply": _services_apply,
}


def _finish(session: Session, job: Job, status: JobStatus, *, result: dict | None = None, error: str | None = None) -> None:
    job.status = status
    job.result = result
    job.error_message = error
    job.finished_at = datetime.now(UTC)
    if status == JobStatus.succeeded:
        job.progress = 100
    session.commit()
    _publish_job(job)


@celery_app.task(name="serverpilot.jobs.run", bind=True, max_retries=5, acks_late=True)
def run_job(self, job_id: str) -> str:
    with get_sync_sessionmaker()() as session:
        job = session.execute(select(Job).where(Job.id == uuid.UUID(job_id))).scalar_one_or_none()
        if job is None:
            logger.error("job not found", extra={"job_id": job_id})
            return "missing"
        if job.status in (JobStatus.cancelled, JobStatus.succeeded):
            return job.status.value

        handler = HANDLERS.get(job.job_type)
        ctx = JobContext(session, job)
        job.status = JobStatus.running
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        session.commit()
        _publish_job(job)

        if handler is None:
            ctx.log(f"No handler registered for job type '{job.job_type}'", level="error")
            _finish(session, job, JobStatus.failed, error="Unsupported job type")
            return "failed"

        ctx.log(f"Started {job.job_type} (attempt {job.attempts})")
        params = dict(job.params or {})
        try:
            result = handler(ctx, params)
        except JobCancelled:
            ctx.log("Cancelled by user", level="warning")
            _finish(session, job, JobStatus.cancelled, error="Cancelled by user")
            _release_lock(params)
            return "cancelled"
        except JobFailed as exc:
            session.rollback()
            ctx.log(str(exc), level="error")
            _finish(session, job, JobStatus.failed, result=exc.result, error=str(exc)[:2000])
            _audit_operation(session, job, "failure")
            _release_lock(params)
            return "failed"
        except SoftTimeLimitExceeded:
            session.rollback()
            ctx.log(f"Timed out after {job.timeout_seconds}s", level="error")
            _finish(session, job, JobStatus.failed, error=f"Timed out after {job.timeout_seconds}s")
            _release_lock(params)
            return "failed"
        except OperationalError as exc:
            session.rollback()
            if job.attempts <= job.max_retries:
                ctx.log(f"Transient error, retrying: {exc.__class__.__name__}", level="warning")
                job.status = JobStatus.queued
                session.commit()
                _publish_job(job)
                raise self.retry(exc=exc, countdown=min(60, 2 ** job.attempts))
            ctx.log(f"Failed: {exc.__class__.__name__}", level="error")
            _finish(session, job, JobStatus.failed, error=str(exc)[:2000])
            _release_lock(params)
            return "failed"
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.exception("job failed", extra={"job_id": job_id})
            ctx.log(f"Failed: {exc}", level="error")
            _finish(session, job, JobStatus.failed, error=str(exc)[:2000])
            _release_lock(params)
            return "failed"

        ctx.log("Completed successfully")
        _finish(session, job, JobStatus.succeeded, result=result)
        _audit_operation(session, job, "success")
        _release_lock(params)
        return "succeeded"


def _audit_operation(session: Session, job: Job, outcome: str) -> None:
    if not job.job_type.startswith(("software.", "services.")):
        return
    from app.models import User
    from app.services.audit import record_audit_sync

    user = session.get(User, job.created_by_id) if job.created_by_id else None
    args = (job.params or {}).get("args") or {}
    record_audit_sync(
        session, f"{job.job_type}.{outcome}", user_id=job.created_by_id,
        actor_label=user.email if user else None, resource_type="job", resource_id=str(job.id),
        outcome=outcome, details={"server_id": (job.params or {}).get("server_id"), "args": args,
                                  "exit_code": (job.result or {}).get("exit_code"), "error": job.error_message},
    )
