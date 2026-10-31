from fastapi import APIRouter

from app.api.v1.routes import accounts, audit, auth, health, jobs, monitoring, servers, services, software, ws

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, accounts, servers, software, services, jobs, audit, monitoring, ws):
    api_router.include_router(module.router)
