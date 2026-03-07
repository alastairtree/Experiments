"""Integration tests for logical replication commands.

Tests cover the full workflow:
  1. prepare   – compare publisher/subscriber tables, write config
  2. setup-publisher – wal_level, replication user, publication
  3. setup-subscriber – create missing tables, subscription
  4. monitor   – pg_stat_replication + slot lag

All tests use real PostgreSQL clusters (no mocking).
"""

from __future__ import annotations

import time
from pathlib import Path

import psycopg
import pytest
from click.testing import CliRunner

from postgres_manager.cli import main
from postgres_manager.config import load_config
from postgres_manager.replication import (
    compare_tables,
    create_replication_user,
    get_replication_stats,
    get_table_columns,
    setup_publication,
    setup_subscription,
)
from tests.conftest import (
    TEST_ADMIN_1,
    TEST_ADMIN_2,
    TEST_CLUSTER_1,
    TEST_CLUSTER_2,
    TEST_DB,
    TEST_PASSWORD_1,
    TEST_PASSWORD_2,
    TEST_PG_VERSION,
    TEST_PORT_1,
    TEST_PORT_2,
    TEST_PUBLICATION,
    TEST_REPL_PASSWORD,
    TEST_REPL_USER,
    TEST_SUBSCRIPTION,
    TEST_TABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tcp_connect(
    port: int,
    user: str,
    password: str,
    db: str = "postgres",
) -> psycopg.Connection[tuple[object, ...]]:
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost",
        port=port,
        user=user,
        password=password,
        dbname=db,
        autocommit=True,
    )
    return conn


def _create_db(port: int, user: str, password: str, db: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db))
        )


def _drop_db(port: int, user: str, password: str, db: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db))
        )


def _create_demo_table(port: int, user: str, password: str, db: str, table: str) -> None:
    from psycopg import sql as psql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            psql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id       SERIAL PRIMARY KEY,
                instance TEXT NOT NULL,
                message  TEXT NOT NULL,
                created  TIMESTAMP WITH TIME ZONE DEFAULT now()
            )
            """).format(psql.Identifier(table))
        )


def _insert_row(port: int, user: str, password: str, db: str, table: str, msg: str) -> None:
    from psycopg import sql as psql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            psql.SQL("INSERT INTO {} (instance, message) VALUES (%s, %s)").format(
                psql.Identifier(table)
            ),
            ("test", msg),
        )


def _fetch_messages(port: int, user: str, password: str, db: str, table: str) -> list[str]:
    from psycopg import sql as psql
    with _tcp_connect(port, user, password, db) as conn:
        rows = conn.execute(
            psql.SQL("SELECT message FROM {} ORDER BY id").format(psql.Identifier(table))
        ).fetchall()
    return [str(r[0]) for r in rows]


def _drop_subscription(port: int, user: str, password: str, db: str, sub: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            sql.SQL("DROP SUBSCRIPTION IF EXISTS {}").format(sql.Identifier(sub))
        )


def _drop_publication(port: int, user: str, password: str, db: str, pub: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            sql.SQL("DROP PUBLICATION IF EXISTS {}").format(sql.Identifier(pub))
        )


def _drop_replication_user(port: int, user: str, password: str, repl_user: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password) as conn:
        conn.execute(
            sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(repl_user))
        )


def _invoke(runner: CliRunner, args: list[str], env: dict[str, str] | None = None) -> object:
    return runner.invoke(main, args, env=env or {}, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def repl_config_path(tmp_path: Path, pg_instances: dict[str, object]) -> Path:
    """Config file pointing at the test clusters; no [replication] section yet."""
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


@pytest.fixture(autouse=True)
def clean_replication_state(pg_instances: dict[str, object]) -> None:
    """Tear down any replication objects and test databases before each test."""
    # Best-effort cleanup – ignore errors if objects don't exist yet
    try:
        _drop_subscription(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_SUBSCRIPTION)
    except Exception:
        pass
    try:
        _drop_publication(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION)
    except Exception:
        pass
    try:
        _drop_replication_user(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_REPL_USER)
    except Exception:
        pass
    _drop_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
    _drop_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)


# ---------------------------------------------------------------------------
# Helper: full setup
# ---------------------------------------------------------------------------


def _full_setup(
    pub_port: int,
    pub_user: str,
    pub_pw: str,
    sub_port: int,
    sub_user: str,
    sub_pw: str,
) -> None:
    """Create the DB and demo table on both publisher and subscriber."""
    _create_db(pub_port, pub_user, pub_pw, TEST_DB)
    _create_demo_table(pub_port, pub_user, pub_pw, TEST_DB, TEST_TABLE)
    _create_db(sub_port, sub_user, sub_pw, TEST_DB)


# ---------------------------------------------------------------------------
# Unit-level replication module tests (no subscription setup)
# ---------------------------------------------------------------------------


class TestGetTableColumns:
    def test_returns_table_after_creation(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)

        from postgres_manager.config import InstanceConfig
        inst = InstanceConfig(
            cluster_name=TEST_CLUSTER_1,
            port=TEST_PORT_1,
            admin_user=TEST_ADMIN_1,
        )
        cols = get_table_columns(inst, TEST_PASSWORD_1, TEST_DB)
        assert ("public", TEST_TABLE) in cols

    def test_empty_database_returns_no_tables(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        from postgres_manager.config import InstanceConfig
        inst = InstanceConfig(
            cluster_name=TEST_CLUSTER_2,
            port=TEST_PORT_2,
            admin_user=TEST_ADMIN_2,
        )
        cols = get_table_columns(inst, TEST_PASSWORD_2, TEST_DB)
        assert len(cols) == 0


class TestCompareTables:
    def test_create_status_when_table_missing_on_subscriber(self) -> None:
        pub_cols = {("public", "mytable"): [("id", "integer"), ("name", "text")]}
        sub_cols: dict[tuple[str, str], list[tuple[str, str]]] = {}
        entries = compare_tables(pub_cols, sub_cols)
        assert len(entries) == 1
        assert entries[0].status == "create"
        assert entries[0].schema == "public"
        assert entries[0].name == "mytable"

    def test_exists_status_when_identical(self) -> None:
        cols = {("public", "t"): [("id", "integer")]}
        entries = compare_tables(cols, cols)
        assert entries[0].status == "exists"

    def test_alter_status_when_subscriber_is_subset(self) -> None:
        pub = {("public", "t"): [("id", "integer"), ("extra", "text")]}
        sub = {("public", "t"): [("id", "integer")]}
        entries = compare_tables(pub, sub)
        assert entries[0].status == "alter"

    def test_incompatible_when_subscriber_has_extra_column(self) -> None:
        pub = {("public", "t"): [("id", "integer")]}
        sub = {("public", "t"): [("id", "integer"), ("extra", "text")]}
        entries = compare_tables(pub, sub)
        assert entries[0].status == "incompatible"


# ---------------------------------------------------------------------------
# CLI integration: prepare command
# ---------------------------------------------------------------------------


class TestReplicationPrepareCLI:
    def test_prepare_writes_replication_config(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        # Create table on publisher only
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        result = _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]

        cfg = load_config(repl_config_path)
        assert cfg.replication is not None
        assert cfg.replication.publisher_instance == TEST_CLUSTER_1
        assert cfg.replication.subscriber_instance == TEST_CLUSTER_2
        assert cfg.replication.replication_user == TEST_REPL_USER
        assert len(cfg.replication.tables) == 1
        assert cfg.replication.tables[0].name == TEST_TABLE
        assert cfg.replication.tables[0].status == "create"

    def test_prepare_marks_existing_table_as_exists(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        # Create same table on both sides
        for port, user, pw in [
            (TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1),
            (TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2),
        ]:
            _create_db(port, user, pw, TEST_DB)
            _create_demo_table(port, user, pw, TEST_DB, TEST_TABLE)

        result = _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]

        cfg = load_config(repl_config_path)
        assert cfg.replication is not None
        assert cfg.replication.tables[0].status == "exists"


# ---------------------------------------------------------------------------
# CLI integration: setup-publisher command
# ---------------------------------------------------------------------------


class TestReplicationSetupPublisherCLI:
    def test_setup_publisher_creates_publication(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )

        # First prepare
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])

        result = _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]

        # Verify the publication exists
        with _tcp_connect(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB) as conn:
            row = conn.execute(
                "SELECT pubname FROM pg_publication WHERE pubname = %s",
                (TEST_PUBLICATION,),
            ).fetchone()
        assert row is not None

        # Verify the replication user exists
        with _tcp_connect(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1) as conn:
            row = conn.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = %s",
                (TEST_REPL_USER,),
            ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# CLI integration: setup-subscriber command
# ---------------------------------------------------------------------------


class TestReplicationSetupSubscriberCLI:
    def test_setup_subscriber_creates_subscription(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )

        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])

        result = _invoke(runner, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]

        # Verify the subscription exists on the subscriber
        with _tcp_connect(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB) as conn:
            row = conn.execute(
                "SELECT subname FROM pg_subscription WHERE subname = %s",
                (TEST_SUBSCRIPTION,),
            ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Full end-to-end replication test
# ---------------------------------------------------------------------------


class TestEndToEndReplication:
    def test_data_replicates_from_publisher_to_subscriber(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """Insert a row on the publisher; verify it appears on the subscriber."""
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )

        # Prepare
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])

        # Setup publisher
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])

        # Setup subscriber
        _invoke(runner, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
        ])

        # Insert a row on the publisher
        _insert_row(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "replicated!")

        # Wait for replication to catch up (up to 10 s)
        deadline = time.monotonic() + 10
        replicated = False
        while time.monotonic() < deadline:
            msgs = _fetch_messages(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)
            if "replicated!" in msgs:
                replicated = True
                break
            time.sleep(0.5)

        assert replicated, "Row did not replicate to subscriber within 10 seconds"


# ---------------------------------------------------------------------------
# CLI integration: monitor command
# ---------------------------------------------------------------------------


class TestReplicationMonitorCLI:
    def _full_replication_setup(
        self,
        runner: CliRunner,
        repl_config_path: Path,
    ) -> None:
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])
        _invoke(runner, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
        ])

    def test_monitor_exits_zero(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._full_replication_setup(runner, repl_config_path)
        time.sleep(2)  # give subscriber time to connect

        result = _invoke(runner, [
            "replication", "monitor",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        assert "Publisher" in result.output  # type: ignore[union-attr]

    def test_monitor_shows_slot_info(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        self._full_replication_setup(runner, repl_config_path)
        time.sleep(2)

        result = _invoke(runner, [
            "replication", "monitor",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        # Should show at least the slot section header
        assert "replication slots" in result.output  # type: ignore[union-attr]

    def test_monitor_without_replication_config_exits_nonzero(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        result = runner.invoke(main, [
            "replication", "monitor",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Sensible default names
# ---------------------------------------------------------------------------


class TestSensibleDefaults:
    def test_prepare_generates_default_publication_and_subscription_names(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """When --publication-name / --subscription-name are omitted, use auto names."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        result = _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            # omit --publication-name and --subscription-name
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]

        cfg = load_config(repl_config_path)
        assert cfg.replication is not None
        assert cfg.replication.publication_name == f"{TEST_CLUSTER_1}_pub"
        assert cfg.replication.subscription_name == f"{TEST_CLUSTER_2}_sub"
        assert cfg.replication.replication_user == "replicator"

    def test_prepare_default_names_shown_in_output(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """The auto-generated names are printed so the user can review them."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        result = _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        out = result.output  # type: ignore[union-attr]
        assert f"{TEST_CLUSTER_1}_pub" in out
        assert f"{TEST_CLUSTER_2}_sub" in out


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_create_table_dry_run_prints_sql_without_creating(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """--dry-run must print SQL and not create the database or table."""
        result = runner.invoke(main, [
            "create-table",
            "--config", str(repl_config_path),
            "--instance", TEST_CLUSTER_1,
            "--password", TEST_PASSWORD_1,
            "--dry-run",
        ], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output
        assert "CREATE TABLE" in result.output

        # The database must NOT have been created
        with _tcp_connect(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1) as conn:
            row = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
            ).fetchone()
        assert row is None

    def test_insert_dry_run_prints_sql_without_inserting(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """--dry-run must print the INSERT and not modify the table."""
        # First create the table for real
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)

        result = runner.invoke(main, [
            "insert",
            "--config", str(repl_config_path),
            "--instance", TEST_CLUSTER_1,
            "--password", TEST_PASSWORD_1,
            "--message", "dry run msg",
            "--dry-run",
        ], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output
        assert "INSERT" in result.output

        # No rows must have been inserted
        msgs = _fetch_messages(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        assert msgs == []

    def test_replication_prepare_dry_run_does_not_write_config(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """prepare --dry-run must not write [replication] to config.toml."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        config_before = repl_config_path.read_text()

        result = runner.invoke(main, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--dry-run",
        ], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output

        # Config file must not have changed
        config_after = repl_config_path.read_text()
        assert config_after == config_before

    def test_replication_setup_publisher_dry_run_prints_sql_no_changes(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """setup-publisher --dry-run must not create the publication or replication user."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_demo_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)

        # Real prepare to populate config
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])

        result = runner.invoke(main, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
            "--dry-run",
        ], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output
        assert "CREATE PUBLICATION" in result.output

        # The publication must NOT exist
        with _tcp_connect(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB) as conn:
            row = conn.execute(
                "SELECT pubname FROM pg_publication WHERE pubname = %s",
                (TEST_PUBLICATION,),
            ).fetchone()
        assert row is None

    def test_replication_setup_subscriber_dry_run_prints_sql_no_subscription(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """setup-subscriber --dry-run must not create the subscription."""
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])

        result = runner.invoke(main, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
            "--dry-run",
        ], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output
        assert "CREATE SUBSCRIPTION" in result.output

        # The subscription must NOT exist
        with _tcp_connect(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB) as conn:
            row = conn.execute(
                "SELECT subname FROM pg_subscription WHERE subname = %s",
                (TEST_SUBSCRIPTION,),
            ).fetchone()
        assert row is None


# ---------------------------------------------------------------------------
# --counts flag on monitor
# ---------------------------------------------------------------------------


class TestMonitorCounts:
    def _full_replication_setup(
        self,
        runner: CliRunner,
        repl_config_path: Path,
    ) -> None:
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])
        _invoke(runner, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
        ])

    def test_counts_shows_row_count_table(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """--counts must display a table with publisher and subscriber counts."""
        self._full_replication_setup(runner, repl_config_path)
        time.sleep(2)  # let subscription sync

        # Insert a row on the publisher and wait for it to replicate
        _insert_row(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "count-me")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if _fetch_messages(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE):
                break
            time.sleep(0.5)

        result = _invoke(runner, [
            "replication", "monitor",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--counts",
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        out = result.output  # type: ignore[union-attr]
        assert "Row count comparison" in out
        assert "Publisher" in out
        assert "Subscriber" in out

    def test_counts_highlights_mismatch(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """--counts must mark rows where publisher != subscriber count."""
        self._full_replication_setup(runner, repl_config_path)
        time.sleep(2)

        # Drop the subscription so replication stops, then insert on publisher.
        # This guarantees publisher count > subscriber count.
        _drop_subscription(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_SUBSCRIPTION)
        _insert_row(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE,
                    "publisher-only-row")

        result = _invoke(runner, [
            "replication", "monitor",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--counts",
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        out = result.output  # type: ignore[union-attr]
        assert "Row count comparison" in out
        # When there's a mismatch, "MISMATCH" and max PK info appear
        assert "MISMATCH" in out


# ---------------------------------------------------------------------------
# Polling after setup-subscriber
# ---------------------------------------------------------------------------


class TestPolling:
    def test_setup_subscriber_output_includes_catch_up_info(
        self,
        runner: CliRunner,
        repl_config_path: Path,
        pg_instances: dict[str, object],
    ) -> None:
        """setup-subscriber must print 'catch-up' monitoring output."""
        _full_setup(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1,
            TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2,
        )
        _invoke(runner, [
            "replication", "prepare",
            "--config", str(repl_config_path),
            "--publisher", TEST_CLUSTER_1,
            "--subscriber", TEST_CLUSTER_2,
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--replication-user", TEST_REPL_USER,
            "--publication-name", TEST_PUBLICATION,
            "--subscription-name", TEST_SUBSCRIPTION,
        ])
        _invoke(runner, [
            "replication", "setup-publisher",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_1,
            "--replication-password", TEST_REPL_PASSWORD,
        ])

        result = _invoke(runner, [
            "replication", "setup-subscriber",
            "--config", str(repl_config_path),
            "--password", TEST_PASSWORD_2,
            "--replication-password", TEST_REPL_PASSWORD,
            "--pub-password", TEST_PASSWORD_1,
        ])
        assert result.exit_code == 0, result.output  # type: ignore[union-attr]
        out = result.output  # type: ignore[union-attr]
        # Must mention catch-up monitoring
        assert "catch" in out.lower() or "lag" in out.lower() or "caught up" in out.lower()
