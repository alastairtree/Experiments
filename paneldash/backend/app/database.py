"""Database connection management with multi-tenant support."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


class DatabaseManager:
    """Manages database connections for central and tenant databases."""

    def __init__(self) -> None:
        """Initialize the database manager."""
        self._central_engine: AsyncEngine | None = None
        self._tenant_engines: dict[str, AsyncEngine] = {}
        self._central_session_factory: async_sessionmaker[AsyncSession] | None = None
        self._tenant_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}

    def get_central_engine(self) -> AsyncEngine:
        """Get or create the central database engine."""
        if self._central_engine is None:
            self._central_engine = create_async_engine(
                settings.central_database_url,
                echo=settings.debug,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._central_engine

    def get_tenant_engine(self, database_url: str) -> AsyncEngine:
        """Get or create a tenant database engine."""
        if database_url not in self._tenant_engines:
            self._tenant_engines[database_url] = create_async_engine(
                database_url,
                echo=settings.debug,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._tenant_engines[database_url]

    def get_central_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the central database session factory."""
        if self._central_session_factory is None:
            engine = self.get_central_engine()
            self._central_session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._central_session_factory

    def get_tenant_session_factory(self, database_url: str) -> async_sessionmaker[AsyncSession]:
        """Get or create a tenant database session factory."""
        if database_url not in self._tenant_session_factories:
            engine = self.get_tenant_engine(database_url)
            self._tenant_session_factories[database_url] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._tenant_session_factories[database_url]

    @asynccontextmanager
    async def get_central_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a central database session."""
        session_factory = self.get_central_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def get_tenant_session(self, database_url: str) -> AsyncGenerator[AsyncSession, None]:
        """Get a tenant database session."""
        session_factory = self.get_tenant_session_factory(database_url)
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close_all(self) -> None:
        """Close all database connections."""
        if self._central_engine is not None:
            await self._central_engine.dispose()
            self._central_engine = None
            self._central_session_factory = None

        for engine in self._tenant_engines.values():
            await engine.dispose()
        self._tenant_engines.clear()
        self._tenant_session_factories.clear()


# Global database manager instance
db_manager = DatabaseManager()


# Dependency for getting central database session
async def get_central_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for central database session."""
    async with db_manager.get_central_session() as session:
        yield session


# Dependency for getting tenant database session
async def get_tenant_db(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for tenant database session."""
    async with db_manager.get_tenant_session(database_url) as session:
        yield session
