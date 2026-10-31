from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permissions
from app.core.responses import ok
from app.models import Job, Server, ServerStatus, User
from app.schemas.jobs import JobOut
from app.services.jobs import job_stats

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/summary", summary="Dashboard summary: server fleet and job activity")
async def summary(_: Annotated[User, Depends(require_permissions("monitoring:read"))], db: DbSession) -> dict:
    rows = (await db.execute(select(Server.status, func.count()).group_by(Server.status))).all()
    by_status = {status.value: count for status, count in rows}
    recent = (await db.execute(select(Job).order_by(Job.created_at.desc()).limit(8))).scalars()
    return ok({
        "servers": {
            "total": sum(by_status.values()),
            "online": by_status.get(ServerStatus.online.value, 0),
            "offline": by_status.get(ServerStatus.offline.value, 0),
            "pending": by_status.get(ServerStatus.pending.value, 0),
        },
        "jobs": (await job_stats(db)).model_dump(),
        "recent_jobs": [JobOut.model_validate(j).model_dump(mode="json") for j in recent],
    })
