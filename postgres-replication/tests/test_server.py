"""Tests for the FastAPI web server.

Unit tests (no DB needed): status, connect, plan, HTML endpoint.
Integration tests (real PG clusters): monitor, drift, apply.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import postgres_manager.server as srv
from postgres_manager.server import app
from tests.conftest import (
    TEST_ADMIN_1,
    TEST_CLUSTER_1,
    TEST_CLUSTER_2,
    TEST_DB,
    TEST_PASSWORD_1,
    TEST_PASSWORD_2,
    TEST_PG_VERSION,
    TEST_PORT_1,
    TEST_PORT_2,
    TEST_PUBLICATION,
    TEST_SUBSCRIPTION,
    TEST_TABLE,
    TEST_REPL_USER,
    TEST_REPL_PASSWORD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_config_override(tmp_path: Path):
    """Redirect all server file I/O to a temp dir, reset after each test."""
    srv._config_override = tmp_path / "config.toml"
    yield
    srv._config_override = None


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def client_with_config(tmp_path: Path, client: TestClient) -> TestClient:
    """Client with a minimal config (no replication) written to disk."""
    srv._config_override.write_text(  # type: ignore[union-attr]
        f"""
[postgres]
version = 16

[[instances]]
cluster_name = "pub"
port = 5432
admin_user = "admin"
socket_dir = "/var/run/postgresql"

[[instances]]
cluster_name = "sub"
port = 5433
admin_user = "admin"
socket_dir = "/var/run/postgresql"

[database]
name = "mydb"

[table]
name = "demo"
"""
    )
    return client


@pytest.fixture()
def client_with_repl_config(tmp_path: Path, pg_instances: dict[str, Any]) -> TestClient:
    """Client with a full test config (with replication section)."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        f"""
[postgres]
version = {TEST_PG_VERSION}

[[instances]]
cluster_name = "{TEST_CLUSTER_1}"
port = {TEST_PORT_1}
admin_user = "{TEST_ADMIN_1}"
socket_dir = "/var/run/postgresql"

[[instances]]
cluster_name = "{TEST_CLUSTER_2}"
port = {TEST_PORT_2}
admin_user = "testadmin2"
socket_dir = "/var/run/postgresql"

[database]
name = "{TEST_DB}"

[table]
name = "{TEST_TABLE}"

[replication]
publisher_instance = "{TEST_CLUSTER_1}"
subscriber_instance = "{TEST_CLUSTER_2}"
publication_name = "{TEST_PUBLICATION}"
subscription_name = "{TEST_SUBSCRIPTION}"
replication_user = "{TEST_REPL_USER}"
"""
    )
    srv._config_override = cfg_path
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------


class TestIndexPage:
    def test_returns_html(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_contains_app_name(self, client: TestClient) -> None:
        assert "postgres-manager" in client.get("/").text

    def test_contains_bootstrap(self, client: TestClient) -> None:
        assert "bootstrap" in client.get("/").text.lower()

    def test_contains_api_fetch(self, client: TestClient) -> None:
        """JS should call /api/status on load."""
        assert "api/status" in client.get("/").text


# ---------------------------------------------------------------------------
# /api/status
# ---------------------------------------------------------------------------


class TestApiStatus:
    def test_no_config_returns_has_config_false(self, client: TestClient) -> None:
        r = client.get("/api/status")
        assert r.status_code == 200
        d = r.json()
        assert d["has_config"] is False

    def test_no_config_includes_config_path(self, client: TestClient) -> None:
        d = client.get("/api/status").json()
        assert "config_path" in d
        assert d["config_path"].endswith("config.toml")

    def test_has_plan_false_when_no_plan(self, client: TestClient) -> None:
        d = client.get("/api/status").json()
        assert d["has_plan"] is False

    def test_with_config_returns_has_config_true(self, client_with_config: TestClient) -> None:
        d = client_with_config.get("/api/status").json()
        assert d["has_config"] is True

    def test_with_config_includes_instances(self, client_with_config: TestClient) -> None:
        d = client_with_config.get("/api/status").json()
        assert len(d["instances"]) == 2
        names = [i["cluster_name"] for i in d["instances"]]
        assert "pub" in names
        assert "sub" in names

    def test_with_config_includes_database(self, client_with_config: TestClient) -> None:
        d = client_with_config.get("/api/status").json()
        assert d["database"] == "mydb"

    def test_with_config_has_replication_false_when_missing(
        self, client_with_config: TestClient
    ) -> None:
        d = client_with_config.get("/api/status").json()
        assert d["has_replication"] is False

    def test_has_plan_true_when_plan_exists(self, tmp_path: Path, client_with_config: TestClient) -> None:
        plan_path = srv._config_override.parent / "replication-plan.json"  # type: ignore[union-attr]
        plan_path.write_text('{"steps":[]}')
        d = client_with_config.get("/api/status").json()
        assert d["has_plan"] is True


# ---------------------------------------------------------------------------
# /api/connect
# ---------------------------------------------------------------------------


class TestApiConnect:
    def _form(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "pg_version": 16,
            "publisher": {
                "cluster_name": "pub1",
                "port": 5432,
                "admin_user": "pgadmin",
                "socket_dir": "/var/run/postgresql",
            },
            "subscriber": {
                "cluster_name": "sub1",
                "port": 5433,
                "admin_user": "pgadmin",
                "socket_dir": "/var/run/postgresql",
            },
            "db_name": "appdb",
            "table_name": "events",
            "replication": None,
        }
        base.update(overrides)
        return base

    def test_creates_config_file(self, client: TestClient) -> None:
        r = client.post("/api/connect", json=self._form())
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert srv._config_override is not None and srv._config_override.exists()

    def test_config_is_valid_toml(self, client: TestClient) -> None:
        client.post("/api/connect", json=self._form())
        data = tomllib.loads(srv._config_override.read_text())  # type: ignore[union-attr]
        assert data["postgres"]["version"] == 16
        assert len(data["instances"]) == 2

    def test_database_section_written(self, client: TestClient) -> None:
        client.post("/api/connect", json=self._form())
        data = tomllib.loads(srv._config_override.read_text())  # type: ignore[union-attr]
        assert data["database"]["name"] == "appdb"
        assert data["table"]["name"] == "events"

    def test_publisher_fields_written(self, client: TestClient) -> None:
        client.post("/api/connect", json=self._form())
        data = tomllib.loads(srv._config_override.read_text())  # type: ignore[union-attr]
        pub = data["instances"][0]
        assert pub["cluster_name"] == "pub1"
        assert pub["port"] == 5432
        assert pub["admin_user"] == "pgadmin"

    def test_replication_section_written_when_provided(self, client: TestClient) -> None:
        form = self._form(
            replication={
                "publication_name": "my_pub",
                "subscription_name": "my_sub",
                "replication_user": "replicator",
            }
        )
        client.post("/api/connect", json=form)
        data = tomllib.loads(srv._config_override.read_text())  # type: ignore[union-attr]
        assert data["replication"]["publication_name"] == "my_pub"
        assert data["replication"]["subscription_name"] == "my_sub"

    def test_no_replication_section_when_null(self, client: TestClient) -> None:
        client.post("/api/connect", json=self._form(replication=None))
        data = tomllib.loads(srv._config_override.read_text())  # type: ignore[union-attr]
        assert "replication" not in data

    def test_status_reflects_new_config(self, client: TestClient) -> None:
        client.post("/api/connect", json=self._form())
        d = client.get("/api/status").json()
        assert d["has_config"] is True
        assert d["database"] == "appdb"

    def test_creates_parent_directory(self, tmp_path: Path, client: TestClient) -> None:
        nested = tmp_path / "nested" / "dir" / "config.toml"
        srv._config_override = nested
        r = client.post("/api/connect", json=self._form())
        assert r.status_code == 200
        assert nested.exists()


# ---------------------------------------------------------------------------
# /api/plan  (GET + PUT — no DB needed)
# ---------------------------------------------------------------------------


class TestApiPlan:
    def test_get_returns_null_when_no_plan(self, client: TestClient) -> None:
        d = client.get("/api/plan").json()
        assert d["plan"] is None

    def test_put_saves_plan(self, client_with_config: TestClient) -> None:
        plan = {"steps": [{"step": 1, "description": "test"}], "needs_full_resync": False}
        r = client_with_config.put("/api/plan", json=plan)
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_get_returns_saved_plan(self, client_with_config: TestClient) -> None:
        plan = {"steps": [{"step": 1, "description": "do something"}], "needs_full_resync": False}
        client_with_config.put("/api/plan", json=plan)
        d = client_with_config.get("/api/plan").json()
        assert d["plan"] is not None
        assert d["plan"]["steps"][0]["description"] == "do something"

    def test_plan_written_to_file(self, client_with_config: TestClient, tmp_path: Path) -> None:
        plan = {"steps": [], "needs_full_resync": False}
        client_with_config.put("/api/plan", json=plan)
        plan_file = srv._config_override.parent / "replication-plan.json"  # type: ignore[union-attr]
        assert plan_file.exists()
        assert json.loads(plan_file.read_text())["steps"] == []


# ---------------------------------------------------------------------------
# /api/apply  (no plan file → 404)
# ---------------------------------------------------------------------------


class TestApiApplyNoplan:
    def test_returns_404_when_no_plan(self, client_with_config: TestClient) -> None:
        r = client_with_config.post(
            "/api/apply",
            json={"pub_password": "pw", "sub_password": "", "dry_run": True},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/monitor  (integration — real clusters)
# ---------------------------------------------------------------------------


class TestApiMonitor:
    def test_monitor_returns_has_replication_false_without_rep_config(
        self, client_with_config: TestClient
    ) -> None:
        """No [replication] in config → has_replication=False, no DB call needed."""
        r = client_with_config.post(
            "/api/monitor",
            json={"pub_password": "any", "sub_password": ""},
        )
        assert r.status_code == 200
        assert r.json()["has_replication"] is False

    def test_monitor_with_real_clusters(
        self, client_with_repl_config: TestClient, pg_instances: dict[str, Any]
    ) -> None:
        """Monitor endpoint returns live data from the publisher cluster."""
        r = client_with_repl_config.post(
            "/api/monitor",
            json={"pub_password": TEST_PASSWORD_1, "sub_password": TEST_PASSWORD_2},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["has_replication"] is True
        assert d["publisher"]["cluster_name"] == TEST_CLUSTER_1
        assert "connections" in d
        assert "slots" in d


# ---------------------------------------------------------------------------
# /api/drift  (integration — real clusters)
# ---------------------------------------------------------------------------


class TestApiDrift:
    def test_drift_returns_400_without_replication_config(
        self, client_with_config: TestClient
    ) -> None:
        r = client_with_config.post(
            "/api/drift",
            json={"pub_password": "any", "sub_password": ""},
        )
        assert r.status_code == 400

    def test_drift_clean_state(
        self, client_with_repl_config: TestClient, pg_instances: dict[str, Any], tmp_path: Path
    ) -> None:
        """Drift scan on clusters with no publication/subscription returns no drift errors."""
        import psycopg
        from psycopg import sql

        # Ensure the test DB exists so detection has something to work with
        for port, admin, pw in [
            (TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1),
            (TEST_PORT_2, "testadmin2", TEST_PASSWORD_2),
        ]:
            conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
                host="localhost", port=port, user=admin, password=pw,
                dbname="postgres", autocommit=True,
            )
            with conn:
                exists = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
                ).fetchone()
                if not exists:
                    conn.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB))
                    )

        r = client_with_repl_config.post(
            "/api/drift",
            json={"pub_password": TEST_PASSWORD_1, "sub_password": TEST_PASSWORD_2},
        )
        assert r.status_code == 200
        d = r.json()
        assert "drift" in d
        assert "plan" in d
        # Plan file should have been saved
        plan_file = srv._config_override.parent / "replication-plan.json"  # type: ignore[union-attr]
        assert plan_file.exists()
