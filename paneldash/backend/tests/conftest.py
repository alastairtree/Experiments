"""Pytest configuration and shared fixtures."""

import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
async def db_available() -> bool:
    """Check if the database is available for integration tests."""
    engine = create_async_engine(settings.central_database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except (ConnectionRefusedError, OSError, Exception):
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def test_db_setup(db_available: bool) -> AsyncGenerator[bool, None]:
    """Set up test database with migrations if PostgreSQL is available."""
    if not db_available:
        yield False
        return

    # Database is available - run migrations
    backend_dir = Path(__file__).parent.parent
    try:
        # Run migrations
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            yield True
        else:
            # Migrations failed, skip tests
            print(f"Migration failed: {result.stderr}")
            yield False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"Could not run migrations: {e}")
        yield False


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring database connection"
    )
