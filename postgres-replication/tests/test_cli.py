"""Integration tests for the Click CLI against real PostgreSQL clusters.

All commands are invoked through Click's CliRunner.  No mocking is used —
every command actually connects to the test clusters created by pg_instances.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from click.testing import CliRunner

from postgres_manager.cli import main
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


def _invoke(
    runner: CliRunner,
    args: list[str],
    env: dict[str, str] | None = None,
) -> object:
    return runner.invoke(main, args, env=env or {}, catch_exceptions=False)


def _drop_db(port: int, user: str, password: str, db: str) -> None:
    from psycopg import sql
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost", port=port, user=user, password=password,
        dbname="postgres", autocommit=True,
    )
    with conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db)))


def _count_rows(port: int, user: str, password: str, db: str, table: str) -> int:
    from psycopg import sql as psql
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost", port=port, user=user, password=password,
        dbname=db, autocommit=True,
    )
    with conn:
        row = conn.execute(
            psql.SQL("SELECT COUNT(*) FROM {}").format(psql.Identifier(table))
        ).fetchone()
    return int(row[0]) if row else 0


def _fetch_rows(port: int, user: str, password: str, db: str, table: str) -> list[dict[str, object]]:
    from psycopg import sql as psql
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost", port=port, user=user, password=password,
        dbname=db, autocommit=True,
    )
    with conn:
        cur = conn.execute(
            psql.SQL("SELECT id, instance, message FROM {} ORDER BY id").format(
                psql.Identifier(table)
            )
        )
        cols = [d[0] for d in cur.description or []]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def clean_db(pg_instances: dict[str, object]) -> None:
    """Drop the test database in both clusters before each test."""
    _drop_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
    _drop_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)


# ---------------------------------------------------------------------------
# create-table command
# ---------------------------------------------------------------------------


class TestCreateTableCommand:
    def test_creates_db_and_table_in_instance1(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        result = _invoke(runner, [
            "create-table",
            "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1,
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        # Verify table exists via direct DB connection
        assert _count_rows(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE) == 0

    def test_creates_db_and_table_in_instance2(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        result = _invoke(runner, [
            "create-table",
            "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_2,
            "--password", TEST_PASSWORD_2,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        assert _count_rows(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE) == 0

    def test_both_instances_get_the_same_table_name(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        for cluster, pw in [(TEST_CLUSTER_1, TEST_PASSWORD_1), (TEST_CLUSTER_2, TEST_PASSWORD_2)]:
            result = _invoke(runner, [
                "create-table",
                "--config", str(test_config_path),
                "--instance", cluster,
                "--password", pw,
            ])
            assert result.exit_code == 0, result.output  # type: ignore[union-attr]

    def test_missing_password_exits_nonzero(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        result = runner.invoke(main, [
            "create-table",
            "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1,
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# insert command
# ---------------------------------------------------------------------------


class TestInsertCommand:
    def _setup(self, runner: CliRunner, config_path: Path, cluster: str, pw: str) -> None:
        _invoke(runner, [
            "create-table", "--config", str(config_path),
            "--instance", cluster, "--password", pw,
        ])

    def test_inserts_row_into_instance1(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._setup(runner, test_config_path, TEST_CLUSTER_1, TEST_PASSWORD_1)
        result = _invoke(runner, [
            "insert",
            "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1,
            "--password", TEST_PASSWORD_1,
            "--message", "row for instance 1",
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        assert _count_rows(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE) == 1

    def test_inserts_row_into_instance2(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._setup(runner, test_config_path, TEST_CLUSTER_2, TEST_PASSWORD_2)
        result = _invoke(runner, [
            "insert",
            "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_2,
            "--password", TEST_PASSWORD_2,
            "--message", "row for instance 2",
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        assert _count_rows(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE) == 1

    def test_two_instances_have_different_rows(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """Insert into both instances and verify they contain different data."""
        # Set up tables
        self._setup(runner, test_config_path, TEST_CLUSTER_1, TEST_PASSWORD_1)
        self._setup(runner, test_config_path, TEST_CLUSTER_2, TEST_PASSWORD_2)

        # Insert a different message into each instance
        _invoke(runner, [
            "insert", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1, "--password", TEST_PASSWORD_1,
            "--message", "unique message for instance 1",
        ])
        _invoke(runner, [
            "insert", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_2, "--password", TEST_PASSWORD_2,
            "--message", "unique message for instance 2",
        ])

        rows1 = _fetch_rows(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        rows2 = _fetch_rows(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)

        assert len(rows1) == 1
        assert len(rows2) == 1
        assert rows1[0]["message"] == "unique message for instance 1"
        assert rows2[0]["message"] == "unique message for instance 2"
        assert rows1[0]["message"] != rows2[0]["message"]


# ---------------------------------------------------------------------------
# query command
# ---------------------------------------------------------------------------


class TestQueryCommand:
    def _setup_with_row(
        self,
        runner: CliRunner,
        config_path: Path,
        cluster: str,
        pw: str,
        message: str,
    ) -> None:
        _invoke(runner, [
            "create-table", "--config", str(config_path),
            "--instance", cluster, "--password", pw,
        ])
        _invoke(runner, [
            "insert", "--config", str(config_path),
            "--instance", cluster, "--password", pw,
            "--message", message,
        ])

    def test_query_instance1_shows_its_data(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._setup_with_row(
            runner, test_config_path, TEST_CLUSTER_1, TEST_PASSWORD_1, "hello from 1"
        )
        result = _invoke(runner, [
            "query", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1, "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0  # type: ignore[union-attr]
        assert "hello from 1" in result.output  # type: ignore[union-attr]

    def test_query_instance2_shows_its_data(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._setup_with_row(
            runner, test_config_path, TEST_CLUSTER_2, TEST_PASSWORD_2, "hello from 2"
        )
        result = _invoke(runner, [
            "query", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_2, "--password", TEST_PASSWORD_2,
        ])
        assert result.exit_code == 0  # type: ignore[union-attr]
        assert "hello from 2" in result.output  # type: ignore[union-attr]

    def test_instances_contain_different_data(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """Query both instances and confirm their data differs."""
        self._setup_with_row(
            runner, test_config_path, TEST_CLUSTER_1, TEST_PASSWORD_1, "data only in inst1"
        )
        self._setup_with_row(
            runner, test_config_path, TEST_CLUSTER_2, TEST_PASSWORD_2, "data only in inst2"
        )

        res1 = _invoke(runner, [
            "query", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1, "--password", TEST_PASSWORD_1,
        ])
        res2 = _invoke(runner, [
            "query", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_2, "--password", TEST_PASSWORD_2,
        ])

        assert "data only in inst1" in res1.output  # type: ignore[union-attr]
        assert "data only in inst2" in res2.output  # type: ignore[union-attr]
        # Each result only contains that instance's message
        assert "data only in inst2" not in res1.output  # type: ignore[union-attr]
        assert "data only in inst1" not in res2.output  # type: ignore[union-attr]

    def test_query_empty_table_shows_no_rows(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        _invoke(runner, [
            "create-table", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1, "--password", TEST_PASSWORD_1,
        ])
        result = _invoke(runner, [
            "query", "--config", str(test_config_path),
            "--instance", TEST_CLUSTER_1, "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0  # type: ignore[union-attr]
        assert "no rows" in result.output  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# --instance flag behaviour
# ---------------------------------------------------------------------------


class TestInstanceSelection:
    def test_error_when_instance_not_specified_for_multi_instance_config(
        self,
        runner: CliRunner,
        test_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """When config has two instances and --instance is omitted, exit non-zero."""
        result = runner.invoke(main, [
            "query",
            "--config", str(test_config_path),
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code != 0

    def test_auto_select_when_single_instance_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """When config has only one instance, --instance can be omitted."""
        single_cfg = tmp_path / "single.toml"
        single_cfg.write_text(f"""
[postgres]
version = 16

[[instances]]
cluster_name = "{TEST_CLUSTER_1}"
port = {TEST_PORT_1}
admin_user = "{TEST_ADMIN_1}"
socket_dir = "/var/run/postgresql"

[database]
name = "{TEST_DB}"

[table]
name = "{TEST_TABLE}"
""")
        # create-table without --instance should work
        result = _invoke(runner, [
            "create-table",
            "--config", str(single_cfg),
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
