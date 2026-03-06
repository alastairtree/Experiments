"""Integration tests for postgres operations against real clusters.

Requires the session-scoped ``pg_instances`` fixture from conftest.py which
creates and starts two real PostgreSQL clusters on ports 25432 and 25433.
"""

from __future__ import annotations

import psycopg
import pytest

from postgres_manager.config import AppConfig, InstanceConfig
from postgres_manager.postgres import (
    PostgresError,
    create_database,
    create_table,
    insert_row,
    query_rows,
)
from tests.conftest import (
    TEST_ADMIN_1,
    TEST_ADMIN_2,
    TEST_CLUSTER_1,
    TEST_CLUSTER_2,
    TEST_DB,
    TEST_PASSWORD_1,
    TEST_PASSWORD_2,
    TEST_PORT_1,
    TEST_PORT_2,
    TEST_TABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tcp_conn(port: int, user: str, password: str, db: str = "postgres") -> psycopg.Connection[tuple[object, ...]]:
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost", port=port, user=user, password=password,
        dbname=db, autocommit=True,
    )
    return conn


def _db_exists(port: int, user: str, password: str, db_name: str) -> bool:
    with _tcp_conn(port, user, password) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
    return row is not None


def _table_exists(port: int, user: str, password: str, db_name: str, table_name: str) -> bool:
    with _tcp_conn(port, user, password, db=db_name) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=%s",
            (table_name,),
        ).fetchone()
    return row is not None


def _drop_db_if_exists(port: int, user: str, password: str, db_name: str) -> None:
    from psycopg import sql
    with _tcp_conn(port, user, password) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
        )


# ---------------------------------------------------------------------------
# Fixture: ensure clean DB state for each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_db(pg_instances: dict[str, object]) -> None:
    """Drop the test database in both clusters before each test."""
    _drop_db_if_exists(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
    _drop_db_if_exists(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)


# ---------------------------------------------------------------------------
# create_database
# ---------------------------------------------------------------------------


class TestCreateDatabase:
    def test_creates_db_in_instance1(self, pg_instances: dict[str, object]) -> None:
        inst = _instance1()
        create_database(inst, TEST_PASSWORD_1, TEST_DB)
        assert _db_exists(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)

    def test_creates_db_in_instance2(self, pg_instances: dict[str, object]) -> None:
        inst = _instance2()
        create_database(inst, TEST_PASSWORD_2, TEST_DB)
        assert _db_exists(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

    def test_idempotent_second_call(self, pg_instances: dict[str, object]) -> None:
        inst = _instance1()
        create_database(inst, TEST_PASSWORD_1, TEST_DB)
        create_database(inst, TEST_PASSWORD_1, TEST_DB)  # should not raise
        assert _db_exists(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)

    def test_two_instances_have_independent_databases(
        self, pg_instances: dict[str, object]
    ) -> None:
        """The same database name can exist separately in each instance."""
        create_database(_instance1(), TEST_PASSWORD_1, TEST_DB)
        create_database(_instance2(), TEST_PASSWORD_2, TEST_DB)
        assert _db_exists(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        assert _db_exists(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)


# ---------------------------------------------------------------------------
# create_table
# ---------------------------------------------------------------------------


class TestCreateTable:
    def test_creates_table_in_instance1(self, pg_instances: dict[str, object]) -> None:
        inst = _instance1()
        create_database(inst, TEST_PASSWORD_1, TEST_DB)
        create_table(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        assert _table_exists(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)

    def test_creates_table_in_instance2(self, pg_instances: dict[str, object]) -> None:
        inst = _instance2()
        create_database(inst, TEST_PASSWORD_2, TEST_DB)
        create_table(inst, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)
        assert _table_exists(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)

    def test_idempotent(self, pg_instances: dict[str, object]) -> None:
        inst = _instance1()
        create_database(inst, TEST_PASSWORD_1, TEST_DB)
        create_table(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        create_table(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)  # should not raise


# ---------------------------------------------------------------------------
# insert_row / query_rows
# ---------------------------------------------------------------------------


class TestInsertAndQuery:
    def _setup_instance(
        self,
        port: int,
        admin: str,
        password: str,
    ) -> None:
        cluster = TEST_CLUSTER_1 if port == TEST_PORT_1 else TEST_CLUSTER_2
        inst = InstanceConfig(
            cluster_name=cluster,
            port=port,
            admin_user=admin,
            socket_dir="/var/run/postgresql",
        )
        create_database(inst, password, TEST_DB)
        create_table(inst, password, TEST_DB, TEST_TABLE)

    def test_insert_returns_id(self, pg_instances: dict[str, object]) -> None:
        self._setup_instance(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1)
        inst = _instance1()
        row_id = insert_row(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "hello")
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_query_returns_inserted_row(self, pg_instances: dict[str, object]) -> None:
        self._setup_instance(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1)
        inst = _instance1()
        insert_row(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "test message")
        rows = query_rows(inst, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        assert len(rows) == 1
        assert rows[0]["message"] == "test message"
        assert rows[0]["instance"] == TEST_CLUSTER_1

    def test_two_instances_hold_different_data(
        self, pg_instances: dict[str, object]
    ) -> None:
        """Core integration test: same table name, independent data per instance."""
        self._setup_instance(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1)
        self._setup_instance(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2)

        inst1 = _instance1()
        inst2 = _instance2()

        insert_row(inst1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "message for instance 1")
        insert_row(inst2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE, "message for instance 2")

        rows1 = query_rows(inst1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        rows2 = query_rows(inst2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)

        assert len(rows1) == 1
        assert len(rows2) == 1
        assert rows1[0]["message"] == "message for instance 1"
        assert rows2[0]["message"] == "message for instance 2"
        # Confirm data is different
        assert rows1[0]["message"] != rows2[0]["message"]
        assert rows1[0]["instance"] != rows2[0]["instance"]

    def test_empty_query_returns_empty_list(self, pg_instances: dict[str, object]) -> None:
        self._setup_instance(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1)
        rows = query_rows(_instance1(), TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        assert rows == []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _instance1() -> InstanceConfig:
    return InstanceConfig(
        cluster_name=TEST_CLUSTER_1,
        port=TEST_PORT_1,
        admin_user=TEST_ADMIN_1,
        socket_dir="/var/run/postgresql",
    )


def _instance2() -> InstanceConfig:
    return InstanceConfig(
        cluster_name=TEST_CLUSTER_2,
        port=TEST_PORT_2,
        admin_user=TEST_ADMIN_2,
        socket_dir="/var/run/postgresql",
    )
