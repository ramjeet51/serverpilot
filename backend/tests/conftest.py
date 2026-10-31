"""Test setup. Environment is pinned before the application is imported."""

import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]


def _env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


_shared = _env_file(ROOT / ".env")
_db_user = _shared["POSTGRES_USER"]
_db_password = _shared["POSTGRES_PASSWORD"]
_db_host = _shared.get("POSTGRES_HOST") or "127.0.0.1"
_db_port = _shared.get("POSTGRES_PORT") or "5432"

os.environ["APP_ENV"] = "test"
os.environ["APP_DEBUG"] = "false"
os.environ["APP_SECRET_KEY"] = "test-app-secret-value-not-for-production"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-value-not-for-production"
os.environ["REQUIRE_MFA"] = "false"
os.environ["API_DOCS_ENABLED"] = "false"
os.environ["COOKIE_SECURE"] = "false"
os.environ["LOGIN_RATE_LIMIT_ATTEMPTS"] = "30"
os.environ["API_RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["INITIAL_ADMIN_EMAIL"] = ""
os.environ["INITIAL_ADMIN_PASSWORD"] = ""
os.environ["DATABASE_URL"] = (
    f"postgresql+psycopg://{quote(_db_user)}:{quote(_db_password)}@{_db_host}:{_db_port}/serverpilot_test"
)
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/15"
os.environ["CELERY_BROKER_URL"] = "redis://127.0.0.1:6379/15"
os.environ["CELERY_RESULT_BACKEND"] = "redis://127.0.0.1:6379/15"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.cli import seed_rbac, upsert_admin
from app.core.config import get_settings
from app.core.database import get_sync_engine, get_sync_sessionmaker
from app.core.redis import get_sync_redis
from app.main import app
from app.models import Base
from app.worker.celery_app import celery_app

get_settings.cache_clear()
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

ADMIN = {"email": "admin@serverpilot.local", "password": "ServerPilot-1"}


@pytest.fixture(scope="session", autouse=True)
def _database():
    engine = get_sync_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    get_sync_redis().flushdb()
    yield
    Base.metadata.drop_all(engine)
    get_sync_redis().flushdb()
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean(_database):
    with get_sync_sessionmaker()() as session:
        session.execute(text("TRUNCATE audit_logs, job_logs, jobs, user_roles, role_permissions, users, roles, permissions RESTART IDENTITY CASCADE"))
        session.commit()
        seed_rbac(session)
        upsert_admin(session, ADMIN["email"], ADMIN["password"])
    get_sync_redis().flushdb()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def login(client: AsyncClient, email: str = ADMIN["email"], password: str = ADMIN["password"]) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    client.headers["Authorization"] = f"Bearer {data['access_token']}"
    return data
