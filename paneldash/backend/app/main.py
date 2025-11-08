"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="PanelDash API",
    description="Multi-tenant operations dashboard API",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
