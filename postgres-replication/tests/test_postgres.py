"""Tests for PostgreSQL operations (using mocks — no real DB required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from postgres_manager.config import AppConfig, InstanceConfig
from postgres_manager.postgres import (
    PostgresError,
    cluster_exists,
    create_admin_user,
    create_cluster,
    create_database,
    create_table,
    create_table_all,
    insert_all,
    insert_row,
    install_all,
    install_postgres,
    query_all,
    query_rows,
    start_all,
    start_cluster,
    stop_cluster,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed(returncode: int = 0, stdout: str = "") -> MagicMock:
    """Return a mock CompletedProcess."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    return mock


# ---------------------------------------------------------------------------
# cluster_exists
# ---------------------------------------------------------------------------


class TestClusterExists:
    """Tests for cluster_exists()."""

    @patch("postgres_manager.postgres._run")
    def test_returns_true_when_listed(self, mock_run: MagicMock) -> None:
        """Returns True when pg_lsclusters lists the cluster."""
        mock_run.return_value = _make_completed(
            stdout="18 main1 5432 online postgres /var/lib/postgresql/18/main1\n"
        )
        assert cluster_exists(18, "main1") is True

    @patch("postgres_manager.postgres._run")
    def test_returns_false_when_not_listed(self, mock_run: MagicMock) -> None:
        """Returns False when cluster is absent from pg_lsclusters output."""
        mock_run.return_value = _make_completed(
            stdout="18 other 5432 online postgres /var/lib/postgresql/18/other\n"
        )
        assert cluster_exists(18, "main1") is False

    @patch("postgres_manager.postgres._run")
    def test_returns_false_on_command_failure(self, mock_run: MagicMock) -> None:
        """Returns False when pg_lsclusters exits non-zero."""
        mock_run.return_value = _make_completed(returncode=1)
        assert cluster_exists(18, "main1") is False


# ---------------------------------------------------------------------------
# create_cluster
# ---------------------------------------------------------------------------


class TestCreateCluster:
    """Tests for create_cluster()."""

    @patch("postgres_manager.postgres.cluster_exists", return_value=False)
    @patch("postgres_manager.postgres._run")
    def test_calls_pg_createcluster(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """pg_createcluster is called with correct arguments."""
        mock_run.return_value = _make_completed()
        create_cluster(18, instance1)

        args = mock_run.call_args[0][0]
        assert "pg_createcluster" in args
        assert "18" in args
        assert "main1" in args
        assert "--port=5432" in args

    @patch("postgres_manager.postgres.cluster_exists", return_value=True)
    @patch("postgres_manager.postgres._run")
    def test_skips_when_already_exists(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """pg_createcluster is not called when cluster already exists."""
        create_cluster(18, instance1)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# start_cluster / stop_cluster
# ---------------------------------------------------------------------------


class TestStartStopCluster:
    """Tests for start_cluster() and stop_cluster()."""

    @patch("postgres_manager.postgres.time.sleep")
    @patch("postgres_manager.postgres._run")
    def test_start_calls_pg_ctlcluster(
        self, mock_run: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """start_cluster invokes pg_ctlcluster start."""
        mock_run.return_value = _make_completed()
        start_cluster(18, "main1")

        args = mock_run.call_args[0][0]
        assert "pg_ctlcluster" in args
        assert "18" in args
        assert "main1" in args
        assert "start" in args

    @patch("postgres_manager.postgres._run")
    def test_stop_calls_pg_ctlcluster(self, mock_run: MagicMock) -> None:
        """stop_cluster invokes pg_ctlcluster stop."""
        mock_run.return_value = _make_completed()
        stop_cluster(18, "main1")

        args = mock_run.call_args[0][0]
        assert "pg_ctlcluster" in args
        assert "stop" in args


# ---------------------------------------------------------------------------
# create_admin_user
# ---------------------------------------------------------------------------


class TestCreateAdminUser:
    """Tests for create_admin_user()."""

    @patch("postgres_manager.postgres._socket_connect")
    def test_creates_role_on_new_instance(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """CREATE ROLE is executed when the role doesn't exist yet."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        create_admin_user(instance1, "secret")

        mock_conn.execute.assert_called_once()
        sql_arg = mock_conn.execute.call_args[0][0]
        # The SQL object should contain CREATE ROLE
        assert "CREATE ROLE" in str(sql_arg)

    @patch("postgres_manager.postgres._socket_connect")
    def test_alters_role_when_already_exists(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """ALTER ROLE is executed when CREATE ROLE raises DuplicateObject."""
        from psycopg import errors

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        # First execute raises DuplicateObject, second should succeed
        mock_conn.execute.side_effect = [
            errors.DuplicateObject("role already exists"),
            None,
        ]

        create_admin_user(instance1, "newpassword")

        assert mock_conn.execute.call_count == 2
        alter_sql_arg = mock_conn.execute.call_args_list[1][0][0]
        assert "ALTER ROLE" in str(alter_sql_arg)


# ---------------------------------------------------------------------------
# create_database
# ---------------------------------------------------------------------------


class TestCreateDatabase:
    """Tests for create_database()."""

    @patch("postgres_manager.postgres._tcp_connect")
    def test_creates_db_when_not_exists(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """CREATE DATABASE is called when db does not exist."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        # SELECT returns None → db does not exist
        mock_conn.execute.return_value.fetchone.return_value = None

        create_database(instance1, "secret", "demodb")

        assert mock_conn.execute.call_count == 2  # SELECT then CREATE

    @patch("postgres_manager.postgres._tcp_connect")
    def test_skips_create_when_db_exists(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """CREATE DATABASE is not called when db already exists."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        # SELECT returns a row → db already exists
        mock_conn.execute.return_value.fetchone.return_value = (1,)

        create_database(instance1, "secret", "demodb")

        # Only the SELECT was called
        assert mock_conn.execute.call_count == 1


# ---------------------------------------------------------------------------
# create_table
# ---------------------------------------------------------------------------


class TestCreateTable:
    """Tests for create_table()."""

    @patch("postgres_manager.postgres._tcp_connect")
    def test_executes_create_table(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """CREATE TABLE IF NOT EXISTS is executed."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        create_table(instance1, "secret", "demodb", "demo")

        mock_conn.execute.assert_called_once()
        sql_str = str(mock_conn.execute.call_args[0][0])
        assert "CREATE TABLE" in sql_str


# ---------------------------------------------------------------------------
# insert_row
# ---------------------------------------------------------------------------


class TestInsertRow:
    """Tests for insert_row()."""

    @patch("postgres_manager.postgres._tcp_connect")
    def test_returns_inserted_id(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """insert_row returns the id returned by RETURNING id."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchone.return_value = (42,)

        result = insert_row(instance1, "secret", "demodb", "demo", "hello")

        assert result == 42

    @patch("postgres_manager.postgres._tcp_connect")
    def test_raises_when_no_id_returned(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """PostgresError is raised when INSERT returns no row."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchone.return_value = None

        with pytest.raises(PostgresError, match="INSERT did not return"):
            insert_row(instance1, "secret", "demodb", "demo", "hello")


# ---------------------------------------------------------------------------
# query_rows
# ---------------------------------------------------------------------------


class TestQueryRows:
    """Tests for query_rows()."""

    @patch("postgres_manager.postgres._tcp_connect")
    def test_returns_list_of_dicts(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """query_rows returns a list of dicts with the expected keys."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("instance",), ("message",), ("created",)]
        mock_cursor.fetchall.return_value = [
            (1, "main1", "Hello from instance 1", "2024-01-01"),
        ]
        mock_conn.execute.return_value = mock_cursor

        rows = query_rows(instance1, "secret", "demodb", "demo")

        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["instance"] == "main1"
        assert rows[0]["message"] == "Hello from instance 1"

    @patch("postgres_manager.postgres._tcp_connect")
    def test_returns_empty_list_when_no_rows(
        self,
        mock_connect: MagicMock,
        instance1: InstanceConfig,
    ) -> None:
        """query_rows returns an empty list when the table is empty."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("instance",), ("message",), ("created",)]
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        rows = query_rows(instance1, "secret", "demodb", "demo")

        assert rows == []


# ---------------------------------------------------------------------------
# High-level orchestration helpers
# ---------------------------------------------------------------------------


class TestInstallAll:
    """Tests for install_all()."""

    @patch("postgres_manager.postgres.create_cluster")
    @patch("postgres_manager.postgres.install_postgres")
    @patch("postgres_manager.postgres.add_pgdg_repo")
    def test_calls_all_steps(
        self,
        mock_repo: MagicMock,
        mock_install: MagicMock,
        mock_create: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """install_all calls repo setup, install, and two cluster creates."""
        install_all(app_config)

        mock_repo.assert_called_once()
        mock_install.assert_called_once_with(18)
        assert mock_create.call_count == 2


class TestStartAll:
    """Tests for start_all()."""

    @patch("postgres_manager.postgres.create_admin_user")
    @patch("postgres_manager.postgres.start_cluster")
    def test_starts_both_clusters_and_creates_users(
        self,
        mock_start: MagicMock,
        mock_create_user: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """start_all starts both clusters and creates admin users."""
        start_all(app_config, "pw1", "pw2")

        assert mock_start.call_count == 2
        assert mock_create_user.call_count == 2
        mock_create_user.assert_any_call(app_config.instance1, "pw1")
        mock_create_user.assert_any_call(app_config.instance2, "pw2")


class TestCreateTableAll:
    """Tests for create_table_all()."""

    @patch("postgres_manager.postgres.create_table")
    @patch("postgres_manager.postgres.create_database")
    def test_creates_db_and_table_for_both(
        self,
        mock_create_db: MagicMock,
        mock_create_tbl: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """create_table_all creates database and table in both instances."""
        create_table_all(app_config, "pw1", "pw2")

        assert mock_create_db.call_count == 2
        assert mock_create_tbl.call_count == 2


class TestInsertAll:
    """Tests for insert_all()."""

    @patch("postgres_manager.postgres.insert_row")
    def test_inserts_into_both_instances(
        self,
        mock_insert: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """insert_all calls insert_row for both instances with different messages."""
        mock_insert.return_value = 1
        insert_all(app_config, "pw1", "pw2")

        assert mock_insert.call_count == 2
        messages = [c[0][4] for c in mock_insert.call_args_list]
        assert messages[0] != messages[1], "Both instances should get different messages"


class TestQueryAll:
    """Tests for query_all()."""

    @patch("postgres_manager.postgres.query_rows")
    def test_returns_rows_from_both_instances(
        self,
        mock_query: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """query_all returns rows from each instance as a tuple."""
        rows1 = [{"id": 1, "instance": "main1", "message": "msg1", "created": "t"}]
        rows2 = [{"id": 1, "instance": "main2", "message": "msg2", "created": "t"}]
        mock_query.side_effect = [rows1, rows2]

        result1, result2 = query_all(app_config, "pw1", "pw2")

        assert result1 == rows1
        assert result2 == rows2
        assert mock_query.call_count == 2
