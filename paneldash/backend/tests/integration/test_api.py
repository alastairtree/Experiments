"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, client: AsyncClient) -> None:
        """Test that the health endpoint returns healthy status."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_health_check_content_type(self, client: AsyncClient) -> None:
        """Test that the health endpoint returns JSON."""
        response = await client.get("/health")

        assert response.headers["content-type"] == "application/json"
