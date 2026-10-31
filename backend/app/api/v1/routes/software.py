import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.deps import DbSession, require_permissions
from app.core.responses import ok
from app.models import SoftwareInventory, User
from app.schemas.jobs import JobOut
from app.schemas.operations import ArchiveInstall, LibraryQuery, ServerScope, SoftwareChange, SoftwareQuery
from app.services.audit import record_audit
from app.services.catalogue import CATALOGUE, category_of, validate_archive_package
from app.services.host_ops import begin_job, call_agent, require_server, save_software, validate_change

router = APIRouter(prefix="/software", tags=["software"])
Reader = Annotated[User, Depends(require_permissions("software:read"))]
Writer = Annotated[User, Depends(require_permissions("software:write"))]


def _catalogue_row(spec, inventory: SoftwareInventory | None) -> dict:
    return {
        "id": spec.id,
        "category": category_of(spec.id),
        "name": spec.name,
        "description": spec.description,
        "packages": list(spec.packages),
        "requires": [{"id": req_id, "name": CATALOGUE[req_id].name} for req_id in spec.requires],
        "service": spec.service,
        "protected_remove": spec.protected_remove,
        "version_selection": True,
        "installed": inventory is not None and inventory.status == "installed",
        "version": inventory.version if inventory else None,
        "candidate_version": inventory.candidate_version if inventory else None,
        "status": inventory.status if inventory else "unknown",
    }


@router.get("/catalogue", summary="Allowlisted software")
async def catalogue(_: Reader) -> dict:
    return ok([_catalogue_row(spec, None) for spec in CATALOGUE.values()])


@router.get("", summary="Catalogue merged with the last inspection of a server")
async def inventory(_: Reader, db: DbSession, server_id: Annotated[uuid.UUID, Query()]) -> dict:
    await require_server(db, server_id)
    rows = (await db.execute(select(SoftwareInventory).where(SoftwareInventory.server_id == server_id))).scalars()
    by_name = {row.package_name: row for row in rows}
    return ok([_catalogue_row(spec, by_name.get(spec.id)) for spec in CATALOGUE.values()])


@router.post("/inspect", summary="Ask the agent which catalogue packages are installed")
async def inspect(body: ServerScope, request: Request, user: Reader, db: DbSession) -> dict:
    await require_server(db, body.server_id)
    result = await call_agent(db, body.server_id, "software.inspect", {})
    await save_software(db, body.server_id, result.get("packages") or [])
    await record_audit(db, "software.inspect", request=request, user=user, resource_type="server",
                       resource_id=str(body.server_id), details={"exit_code": result.get("exit_code")})
    return ok(result)


@router.post("/versions", summary="Package versions available from APT")
async def versions(body: SoftwareQuery, request: Request, user: Reader, db: DbSession) -> dict:
    spec = CATALOGUE.get(body.software_id)
    if spec is None:
        from app.core.responses import ApiError
        raise ApiError(400, "unknown_software", "That software is not in the catalogue")
    result = await call_agent(db, body.server_id, "software.versions", {"software_id": spec.id})
    await record_audit(db, "software.versions", request=request, user=user, resource_type="software",
                       resource_id=spec.id, details={"server_id": str(body.server_id)})
    return ok(result)


@router.post("/library", summary="Search the Ubuntu package archive on a server")
async def library(body: LibraryQuery, request: Request, user: Reader, db: DbSession) -> dict:
    await require_server(db, body.server_id)
    result = await call_agent(db, body.server_id, "software.library", {"query": body.query.strip()}, timeout=30)
    await record_audit(db, "software.library", request=request, user=user, resource_type="server",
                       resource_id=str(body.server_id), details={"query": body.query.strip()[:40]})
    return ok(result)


@router.post("/archive", status_code=201, summary="Install one package from the Ubuntu archive")
async def install_archive(body: ArchiveInstall, request: Request, user: Writer, db: DbSession) -> dict:
    if not body.confirm:
        from app.core.responses import ApiError
        raise ApiError(400, "confirmation_required", "Confirm this install before it runs")
    try:
        package = validate_archive_package(body.package)
    except ValueError as exc:
        from app.core.responses import ApiError
        raise ApiError(400, "invalid_package", str(exc)) from exc
    server = await require_server(db, body.server_id)
    job = await begin_job(db, user, "software.apply", server, {"action": "install", "source": "archive", "package": package})
    await record_audit(db, "software.archive_install", request=request, user=user, resource_type="software",
                       resource_id=package, details={"server_id": str(server.id), "job_id": str(job.id)})
    return ok(JobOut.model_validate(job).model_dump(mode="json"))


@router.post("/operations", status_code=201, summary="Install, update or remove an allowlisted package")
async def operate(body: SoftwareChange, request: Request, user: Writer, db: DbSession) -> dict:
    spec = validate_change(body.software_id, body.action, body.version, body.confirm)
    server = await require_server(db, body.server_id)
    job = await begin_job(db, user, "software.apply", server, {
        "action": body.action, "software_id": spec.id, "version": body.version,
    })
    await record_audit(db, f"software.{body.action}", request=request, user=user, resource_type="software",
                       resource_id=spec.id, details={"server_id": str(server.id), "job_id": str(job.id),
                                                     "version": body.version})
    return ok(JobOut.model_validate(job).model_dump(mode="json"))
