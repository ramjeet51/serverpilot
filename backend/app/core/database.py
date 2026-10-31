from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_async_engine() -> AsyncEngine:
    s = get_settings()
    return create_async_engine(
        s.sqlalchemy_url,
        pool_size=s.database_pool_size,
        max_overflow=s.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


@lru_cache
def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


@lru_cache
def get_sync_engine() -> Engine:
    """Synchronous engine used by Celery workers and CLI commands."""
    s = get_settings()
    return create_engine(s.sqlalchemy_url, pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800)


@lru_cache
def get_sync_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(get_sync_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_async_sessionmaker()() as session:
        yield session
