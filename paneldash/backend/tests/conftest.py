"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncGenerator

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


@pytest.fixture
async def db_available() -> bool:
    """Check if the database is available for integration tests."""
    engine = create_async_engine(settings.central_database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except (ConnectionRefusedError, OSError):
        return False
    finally:
        await engine.dispose()


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring database connection"
    )
