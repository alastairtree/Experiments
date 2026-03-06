"""Shared pytest fixtures for postgres-manager tests.

Integration tests require a real PostgreSQL installation.  The session-scoped
``pg_instances`` fixture creates two temporary clusters (using pg_createcluster),
starts them, and tears them down when the session ends.

The clusters use ports 25432 and 25433 to avoid clashing with any other
running PostgreSQL service.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest

from postgres_manager.config import AppConfig, DatabaseConfig, InstanceConfig

# ---------------------------------------------------------------------------
# Constants for the test clusters
# ---------------------------------------------------------------------------

TEST_PG_VERSION = 16          # Use the version that is already installed
TEST_PORT_1 = 25432
TEST_PORT_2 = 25433
TEST_CLUSTER_1 = "pytest1"
TEST_CLUSTER_2 = "pytest2"
TEST_ADMIN_1 = "testadmin1"
TEST_ADMIN_2 = "testadmin2"
TEST_PASSWORD_1 = "testpw_one_123"
TEST_PASSWORD_2 = "testpw_two_456"
TEST_DB = "testdb"
TEST_TABLE = "demo"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _cluster_exists(version: int, name: str) -> bool:
    result = _run(["pg_lsclusters", "-h"], check=False)
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == str(version) and parts[1] == name:
            return True
    return False


def _cluster_running(version: int, name: str) -> bool:
    result = _run(["pg_lsclusters", "-h"], check=False)
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == str(version) and parts[1] == name:
            return parts[3] == "online"
    return False


def _create_cluster(version: int, name: str, port: int) -> None:
    if not _cluster_exists(version, name):
        _run([
            "pg_createcluster",
            str(version), name,
            f"--port={port}",
            "--",
            "--auth-local=trust",
            "--auth-host=scram-sha-256",
        ])


def _start_cluster(version: int, name: str) -> None:
    if not _cluster_running(version, name):
        _run(["pg_ctlcluster", str(version), name, "start"])
        time.sleep(2)


def _stop_cluster(version: int, name: str) -> None:
    if _cluster_running(version, name):
        _run(["pg_ctlcluster", str(version), name, "stop", "--", "-m", "fast"], check=False)


def _drop_cluster(version: int, name: str) -> None:
    _run(["pg_dropcluster", "--stop", str(version), name], check=False)


def _socket_connect(port: int, user: str = "postgres") -> psycopg.Connection[tuple[object, ...]]:
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="/var/run/postgresql",
        port=port,
        user=user,
        dbname="postgres",
        autocommit=True,
    )
    return conn


def _ensure_admin_user(port: int, admin_user: str, password: str) -> None:
    from psycopg import errors, sql
    role_ident = sql.Identifier(admin_user)
    pw_literal = sql.Literal(password)
    with _socket_connect(port) as conn:
        try:
            conn.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN SUPERUSER PASSWORD {}").format(
                    role_ident, pw_literal
                )
            )
        except errors.DuplicateObject:
            conn.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN SUPERUSER PASSWORD {}").format(
                    role_ident, pw_literal
                )
            )


# ---------------------------------------------------------------------------
# Session-scoped fixture: two live postgres clusters
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_instances() -> Generator[dict[str, object], None, None]:
    """Create and start two test postgres clusters for the session.

    Yields a dict with the test config details.  Clusters are torn down
    after the session.
    """
    # Setup
    _create_cluster(TEST_PG_VERSION, TEST_CLUSTER_1, TEST_PORT_1)
    _create_cluster(TEST_PG_VERSION, TEST_CLUSTER_2, TEST_PORT_2)
    _start_cluster(TEST_PG_VERSION, TEST_CLUSTER_1)
    _start_cluster(TEST_PG_VERSION, TEST_CLUSTER_2)
    _ensure_admin_user(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1)
    _ensure_admin_user(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2)

    yield {
        "pg_version": TEST_PG_VERSION,
        "port1": TEST_PORT_1,
        "port2": TEST_PORT_2,
        "admin1": TEST_ADMIN_1,
        "admin2": TEST_ADMIN_2,
        "password1": TEST_PASSWORD_1,
        "password2": TEST_PASSWORD_2,
    }

    # Teardown
    _stop_cluster(TEST_PG_VERSION, TEST_CLUSTER_1)
    _stop_cluster(TEST_PG_VERSION, TEST_CLUSTER_2)
    _drop_cluster(TEST_PG_VERSION, TEST_CLUSTER_1)
    _drop_cluster(TEST_PG_VERSION, TEST_CLUSTER_2)


# ---------------------------------------------------------------------------
# Per-test config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_config_path(tmp_path: Path, pg_instances: dict[str, object]) -> Path:
    """Write a temporary config.toml pointing at the test clusters."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
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
admin_user = "{TEST_ADMIN_2}"
socket_dir = "/var/run/postgresql"

[database]
name = "{TEST_DB}"

[table]
name = "{TEST_TABLE}"
"""
    )
    return cfg


@pytest.fixture()
def app_config(test_config_path: Path) -> AppConfig:
    """Return a loaded AppConfig for the test clusters."""
    from postgres_manager.config import load_config
    return load_config(test_config_path)


@pytest.fixture()
def fresh_db(pg_instances: dict[str, object]) -> None:
    """Drop and recreate the test database in both clusters before each test."""
    from psycopg import sql

    for port, admin, password in [
        (TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1),
        (TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2),
    ]:
        conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
            host="localhost",
            port=port,
            user=admin,
            password=password,
            dbname="postgres",
            autocommit=True,
        )
        with conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(TEST_DB))
            )
