"""Pytest configuration and shared fixtures."""

import os
import subprocess
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from tempfile import mkdtemp

import pytest
from httpx import ASGITransport, AsyncClient
from pgserver import get_server  # type: ignore[attr-defined]
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.main import app


@pytest.fixture
async def client(test_db_url: str) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    # Override the database dependency to use test database
    from collections.abc import AsyncGenerator as AG

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.database import get_central_db

    engine = create_async_engine(test_db_url, echo=False)
    test_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_central_db() -> AG[AsyncSession, None]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_central_db] = override_get_central_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up override
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture(scope="session")
def postgres_server() -> Generator:  # type: ignore[type-arg]
    """Create a temporary PostgreSQL server for tests."""
    # Create a temporary directory for the PostgreSQL data
    pgdata = Path(mkdtemp())

    # Get a PostgreSQL server instance (will be cleaned up automatically)
    server = get_server(pgdata, cleanup_mode="delete")

    # Start the server
    with server:
        server.ensure_pgdata_inited()
        server.ensure_postgres_running()
        yield server


@pytest.fixture(scope="session")
def test_db_url(postgres_server) -> str:  # type: ignore[no-untyped-def]
    """Get the test database URL."""
    # Get the connection URI from the server
    uri: str = postgres_server.get_uri()

    # Convert to asyncpg format (replace postgresql:// with postgresql+asyncpg://)
    return uri.replace("postgresql://", "postgresql+asyncpg://")


@pytest.fixture(scope="session")
def run_migrations(postgres_server, test_db_url: str) -> None:  # type: ignore[no-untyped-def]  # noqa: ARG001
    """Run database migrations on the test database."""
    backend_dir = Path(__file__).parent.parent

    # Get connection info from the URI
    info = postgres_server.get_postmaster_info()

    # Temporarily override database URL for migrations
    original_vars = {}

    # pgserver uses Unix domain sockets by default, use socket_dir if available
    if info.socket_dir:
        env_vars = {
            "CENTRAL_DB_HOST": str(info.socket_dir),
            "CENTRAL_DB_PORT": str(info.port) if info.port else "5432",
            "CENTRAL_DB_NAME": "postgres",
            "CENTRAL_DB_USER": "postgres",
            "CENTRAL_DB_PASSWORD": "",
        }
    else:
        env_vars = {
            "CENTRAL_DB_HOST": info.hostname or "localhost",
            "CENTRAL_DB_PORT": str(info.port) if info.port else "5432",
            "CENTRAL_DB_NAME": "postgres",
            "CENTRAL_DB_USER": "postgres",
            "CENTRAL_DB_PASSWORD": "",
        }

    for key, value in env_vars.items():
        original_vars[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Run migrations
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Migration failed: {result.stderr}")
    finally:
        # Restore original environment
        for key, original_value in original_vars.items():
            if original_value is not None:
                os.environ[key] = original_value
            else:
                os.environ.pop(key, None)


@pytest.fixture
async def test_db(postgres_server, run_migrations: None, test_db_url: str) -> AsyncGenerator[None, None]:  # type: ignore[no-untyped-def]  # noqa: ARG001
    """Provide a test database with migrations applied."""
    # Verify database is accessible
    engine = create_async_engine(test_db_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        yield
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(test_db: None, test_db_url: str) -> AsyncGenerator[AsyncSession, None]:  # noqa: ARG001
    """Provide a database session for tests."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = create_async_engine(test_db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        # Note: We don't commit here because API endpoints handle their own transactions
        # Tests should use unique IDs to avoid conflicts

    await engine.dispose()


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring database connection"
    )
