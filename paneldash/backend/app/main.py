"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    # Initialize database connections (done lazily, but we can test connection here)
    try:
        # Test central database connection
        engine = db_manager.get_central_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Warning: Could not connect to central database: {e}")

    yield

    # Shutdown
    await db_manager.close_all()


app = FastAPI(
    title="PanelDash API",
    description="Multi-tenant operations dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
