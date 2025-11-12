"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from app.database import db_manager
import logging

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

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s | %(levelname)-8s | "
                           "%(module)s:%(funcName)s:%(lineno)d - %(message)s")

# Import routers
from app.api.v1 import auth, dashboards, panels, tenants, users  # noqa: E402

# Register API v1 routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(dashboards.router, prefix="/api/v1/dashboards", tags=["dashboards"])
app.include_router(panels.router, prefix="/api/v1/panels", tags=["panels"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
