"""Integration tests for schema evolution commands: detect-drift, plan-repair, apply-repair.

Tests cover:
  - detect_drift: no drift, new table, dropped table, missing on subscriber, schema change
  - plan_repair: correct phase/target labelling from drift reports
  - apply_repair_step: dry-run and real execution
  - CLI: detect-drift, plan-repair, apply-repair commands

All tests use real PostgreSQL clusters (no mocking).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import psycopg
import pytest
from click.testing import CliRunner, Result

from postgres_manager.cli import main
from postgres_manager.config import InstanceConfig, ReplicationConfig
from postgres_manager.schema_evolution import (
    ColumnDiff,
    DriftReport,
    RepairPlan,
    RepairStep,
    TableDrift,
    _compare_columns,
    detect_drift,
    get_all_user_tables,
    get_publication_tables,
    get_replica_identity,
    get_table_columns,
    plan_repair,
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
        result = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db,)
        ).fetchone()
        if result is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))


def _drop_db(port: int, user: str, password: str, db: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db)))


def _create_table(
    port: int, user: str, password: str, db: str, table: str, schema: str = "public"
) -> None:
    from psycopg import sql as psql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            psql.SQL("""
            CREATE TABLE IF NOT EXISTS {schema}.{table} (
                id       SERIAL PRIMARY KEY,
                instance TEXT NOT NULL,
                message  TEXT NOT NULL,
                created  TIMESTAMP WITH TIME ZONE DEFAULT now()
            )
            """).format(
                schema=psql.Identifier(schema),
                table=psql.Identifier(table),
            )
        )


def _create_publication(port: int, user: str, password: str, db: str, pub: str, tables: list[str]) -> None:
    from psycopg import sql as psql
    with _tcp_connect(port, user, password, db) as conn:
        if tables:
            table_ids = psql.SQL(", ").join(psql.Identifier(t) for t in tables)
            conn.execute(
                psql.SQL("CREATE PUBLICATION {} FOR TABLE {}").format(
                    psql.Identifier(pub), table_ids
                )
            )
        else:
            conn.execute(
                psql.SQL("CREATE PUBLICATION {}").format(psql.Identifier(pub))
            )


def _drop_publication(port: int, user: str, password: str, db: str, pub: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            sql.SQL("DROP PUBLICATION IF EXISTS {}").format(sql.Identifier(pub))
        )


def _drop_subscription(port: int, user: str, password: str, db: str, sub: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password, db) as conn:
        conn.execute(
            sql.SQL("DROP SUBSCRIPTION IF EXISTS {}").format(sql.Identifier(sub))
        )


def _drop_role(port: int, user: str, password: str, role: str) -> None:
    from psycopg import sql
    with _tcp_connect(port, user, password) as conn:
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def _add_column(
    port: int, user: str, password: str, db: str, table: str, col: str, col_type: str
) -> None:
    with _tcp_connect(port, user, password, db) as conn:
        stmt = f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
        conn.execute(stmt.encode())


def _pub_instance() -> InstanceConfig:
    return InstanceConfig(cluster_name=TEST_CLUSTER_1, port=TEST_PORT_1, admin_user=TEST_ADMIN_1)


def _sub_instance() -> InstanceConfig:
    return InstanceConfig(cluster_name=TEST_CLUSTER_2, port=TEST_PORT_2, admin_user=TEST_ADMIN_2)


def _repl_config() -> ReplicationConfig:
    return ReplicationConfig(
        publisher_instance=TEST_CLUSTER_1,
        subscriber_instance=TEST_CLUSTER_2,
        publication_name=TEST_PUBLICATION,
        subscription_name=TEST_SUBSCRIPTION,
        replication_user=TEST_REPL_USER,
    )


def _invoke(runner: CliRunner, args: list[str], env: dict[str, str] | None = None) -> Result:
    return runner.invoke(main, args, env=env or {}, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def schema_config_path(tmp_path: Path, pg_instances: dict[str, object]) -> Path:
    """Config with [replication] section, pointing at test clusters."""
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

[replication]
publisher_instance = "{TEST_CLUSTER_1}"
subscriber_instance = "{TEST_CLUSTER_2}"
publication_name = "{TEST_PUBLICATION}"
subscription_name = "{TEST_SUBSCRIPTION}"
replication_user = "{TEST_REPL_USER}"
"""
    )
    return cfg


@pytest.fixture(autouse=True)
def clean_schema_state(pg_instances: dict[str, object]) -> None:
    """Drop replication objects and test databases before each test."""
    for fn in [
        lambda: _drop_subscription(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_SUBSCRIPTION),
        lambda: _drop_publication(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION),
        lambda: _drop_role(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_REPL_USER),
        lambda: _drop_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB),
        lambda: _drop_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB),
    ]:
        try:
            fn()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Unit tests: _compare_columns
# ---------------------------------------------------------------------------


class TestCompareColumns:
    def test_no_diff_when_identical(self) -> None:
        pub = {"id": "int4", "name": "text"}
        sub = {"id": "int4", "name": "text"}
        diffs = _compare_columns(pub, sub, "public", "t")
        assert diffs == []

    def test_missing_on_subscriber(self) -> None:
        pub = {"id": "int4", "name": "text", "email": "text"}
        sub = {"id": "int4", "name": "text"}
        diffs = _compare_columns(pub, sub, "public", "t")
        assert len(diffs) == 1
        assert diffs[0].name == "email"
        assert diffs[0].issue == "missing_on_subscriber"
        assert diffs[0].publisher_type == "text"

    def test_missing_on_publisher(self) -> None:
        pub = {"id": "int4"}
        sub = {"id": "int4", "extra": "text"}
        diffs = _compare_columns(pub, sub, "public", "t")
        assert len(diffs) == 1
        assert diffs[0].name == "extra"
        assert diffs[0].issue == "missing_on_publisher"
        assert diffs[0].subscriber_type == "text"

    def test_type_mismatch(self) -> None:
        pub = {"id": "int4", "amount": "numeric"}
        sub = {"id": "int4", "amount": "int4"}
        diffs = _compare_columns(pub, sub, "public", "t")
        assert len(diffs) == 1
        assert diffs[0].name == "amount"
        assert diffs[0].issue == "type_mismatch"
        assert diffs[0].publisher_type == "numeric"
        assert diffs[0].subscriber_type == "int4"


# ---------------------------------------------------------------------------
# Unit tests: DriftReport / RepairPlan serialisation
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_drift_report_roundtrip(self) -> None:
        drift = TableDrift(
            schema="public",
            table="orders",
            issues=["schema_changed"],
            column_diffs=[
                ColumnDiff(
                    name="email",
                    issue="missing_on_subscriber",
                    publisher_type="text",
                    suggestion="ALTER TABLE ...",
                )
            ],
        )
        report = DriftReport(
            detected_at="2026-01-01T00:00:00+00:00",
            publisher_instance="pub",
            subscriber_instance="sub",
            database="mydb",
            publication_name="mypub",
            subscription_name="mysub",
            table_drifts=[drift],
        )
        restored = DriftReport.from_json(report.to_json())
        assert restored.publisher_instance == "pub"
        assert len(restored.table_drifts) == 1
        assert restored.table_drifts[0].table == "orders"
        assert restored.table_drifts[0].column_diffs[0].name == "email"

    def test_repair_plan_roundtrip(self) -> None:
        step = RepairStep(
            step=1,
            phase=1,
            target="publisher",
            description="[PUBLISHER] Remove table",
            sql=["ALTER PUBLICATION mypub DROP TABLE t;"],
            risk="medium",
        )
        plan = RepairPlan(
            generated_at="2026-01-01T00:00:00+00:00",
            publisher_instance="pub",
            subscriber_instance="sub",
            database="mydb",
            publication_name="mypub",
            subscription_name="mysub",
            steps=[step],
        )
        restored = RepairPlan.from_json(plan.to_json())
        assert len(restored.steps) == 1
        assert restored.steps[0].target == "publisher"
        assert restored.steps[0].phase == 1


# ---------------------------------------------------------------------------
# Integration tests: detect_drift
# ---------------------------------------------------------------------------


class TestDetectDrift:
    def test_detects_new_unconfigured_table(self, pg_instances: dict[str, object]) -> None:
        """Table exists on publisher but is not in the publication."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, "new_table")
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_table(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)
        # Publication covers only TEST_TABLE, not new_table
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        report = detect_drift(
            _pub_instance(), TEST_PASSWORD_1,
            _sub_instance(), TEST_PASSWORD_2,
            _repl_config(), TEST_DB,
        )

        new_tables = [d for d in report.table_drifts if "new_unconfigured" in d.issues]
        assert any(d.table == "new_table" for d in new_tables), (
            f"Expected new_table in new_unconfigured drift, got: {report.table_drifts}"
        )

    def test_detects_missing_on_subscriber(self, pg_instances: dict[str, object]) -> None:
        """Table in publication but not yet created on subscriber."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        # Subscriber has the database but NOT the table
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        report = detect_drift(
            _pub_instance(), TEST_PASSWORD_1,
            _sub_instance(), TEST_PASSWORD_2,
            _repl_config(), TEST_DB,
        )

        missing = [d for d in report.table_drifts if "missing_on_subscriber" in d.issues]
        assert any(d.table == TEST_TABLE for d in missing)

    def test_detects_schema_changed(self, pg_instances: dict[str, object]) -> None:
        """Column added on publisher but not on subscriber."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_table(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)

        # Add a column only on the publisher
        _add_column(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE, "new_col", "TEXT"
        )

        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        report = detect_drift(
            _pub_instance(), TEST_PASSWORD_1,
            _sub_instance(), TEST_PASSWORD_2,
            _repl_config(), TEST_DB,
        )

        changed = [d for d in report.table_drifts if "schema_changed" in d.issues]
        assert any(d.table == TEST_TABLE for d in changed)
        for d in changed:
            if d.table == TEST_TABLE:
                col_names = [c.name for c in d.column_diffs]
                assert "new_col" in col_names
                missing_cols = [c for c in d.column_diffs if c.issue == "missing_on_subscriber"]
                assert any(c.name == "new_col" for c in missing_cols)

    def test_no_drift_when_in_sync(self, pg_instances: dict[str, object]) -> None:
        """Identical tables on both sides — no schema drift."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_table(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        report = detect_drift(
            _pub_instance(), TEST_PASSWORD_1,
            _sub_instance(), TEST_PASSWORD_2,
            _repl_config(), TEST_DB,
        )

        assert report.table_drifts == [], f"Expected no drift, got: {report.table_drifts}"

    def test_drift_report_includes_database_info(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, []
        )

        report = detect_drift(
            _pub_instance(), TEST_PASSWORD_1,
            _sub_instance(), TEST_PASSWORD_2,
            _repl_config(), TEST_DB,
        )

        assert report.publisher_instance == TEST_CLUSTER_1
        assert report.subscriber_instance == TEST_CLUSTER_2
        assert report.database == TEST_DB
        assert report.publication_name == TEST_PUBLICATION
        assert report.subscription_name == TEST_SUBSCRIPTION


# ---------------------------------------------------------------------------
# Integration tests: get_publication_tables / get_all_user_tables / get_replica_identity
# ---------------------------------------------------------------------------


class TestDetectDriftHelpers:
    def test_get_all_user_tables(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        tables = get_all_user_tables(_pub_instance(), TEST_PASSWORD_1, TEST_DB)
        assert ("public", TEST_TABLE) in tables

    def test_get_publication_tables(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )
        tables = get_publication_tables(
            _pub_instance(), TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION
        )
        assert ("public", TEST_TABLE) in tables

    def test_get_table_columns(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        cols = get_table_columns(_pub_instance(), TEST_PASSWORD_1, TEST_DB, "public", TEST_TABLE)
        assert "id" in cols
        assert "message" in cols

    def test_get_replica_identity_with_pk(self, pg_instances: dict[str, object]) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        ri = get_replica_identity(_pub_instance(), TEST_PASSWORD_1, TEST_DB, "public", TEST_TABLE)
        # Table has a PK (SERIAL PRIMARY KEY) → replica identity 'd' (default)
        assert ri == "d"


# ---------------------------------------------------------------------------
# Unit tests: plan_repair
# ---------------------------------------------------------------------------


class TestPlanRepair:
    def _base_report(self) -> DriftReport:
        return DriftReport(
            detected_at="2026-01-01T00:00:00+00:00",
            publisher_instance=TEST_CLUSTER_1,
            subscriber_instance=TEST_CLUSTER_2,
            database=TEST_DB,
            publication_name=TEST_PUBLICATION,
            subscription_name=TEST_SUBSCRIPTION,
            table_drifts=[],
        )

    def test_empty_drift_produces_no_steps(self) -> None:
        report = self._base_report()
        plan = plan_repair(report, TEST_REPL_USER)
        assert plan.steps == []

    def test_new_unconfigured_table_creates_publisher_step(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="orders", issues=["new_unconfigured"])
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        pub_steps = [s for s in plan.steps if s.target == "publisher"]
        assert len(pub_steps) >= 1
        # Should contain ALTER PUBLICATION ADD TABLE
        all_sql = " ".join(stmt for step in pub_steps for stmt in step.sql)
        assert "ADD TABLE" in all_sql
        assert "orders" in all_sql

    def test_dropped_table_creates_publisher_step(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="old_tbl", issues=["dropped_from_publisher"])
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        pub_steps = [s for s in plan.steps if s.target == "publisher" and s.phase == 1]
        assert len(pub_steps) == 1
        assert "DROP TABLE" in pub_steps[0].sql[0]

    def test_missing_on_subscriber_creates_subscriber_step(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="users", issues=["missing_on_subscriber"])
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        sub_steps = [s for s in plan.steps if s.target == "subscriber"]
        assert any(s.phase == 2 for s in sub_steps)

    def test_schema_changed_creates_subscriber_phase2_step(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(
                schema="public",
                table="demo",
                issues=["schema_changed"],
                column_diffs=[
                    ColumnDiff(
                        name="email",
                        issue="missing_on_subscriber",
                        publisher_type="text",
                        suggestion="ALTER TABLE public.demo ADD COLUMN email text;",
                    )
                ],
            )
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        sub2 = [s for s in plan.steps if s.target == "subscriber" and s.phase == 2]
        assert len(sub2) == 1
        assert "ALTER TABLE" in " ".join(sub2[0].sql)

    def test_refresh_step_added_for_new_tables(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="orders", issues=["new_unconfigured"])
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        phase3 = [s for s in plan.steps if s.phase == 3]
        assert len(phase3) == 1
        assert phase3[0].target == "subscriber"
        assert "REFRESH" in " ".join(phase3[0].sql)

    def test_step_labels_include_publisher_subscriber(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="orders", issues=["new_unconfigured"]),
            TableDrift(schema="public", table="users", issues=["missing_on_subscriber"]),
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        for step in plan.steps:
            assert step.target in ("publisher", "subscriber")
            assert f"[{step.target.upper()}]" in step.description, (
                f"Description missing target label: {step.description}"
            )

    def test_steps_are_numbered_sequentially(self) -> None:
        report = self._base_report()
        report.table_drifts = [
            TableDrift(schema="public", table="t1", issues=["new_unconfigured"]),
            TableDrift(schema="public", table="t2", issues=["missing_on_subscriber"]),
        ]
        plan = plan_repair(report, TEST_REPL_USER)
        step_nums = [s.step for s in plan.steps]
        assert step_nums == list(range(1, len(plan.steps) + 1))

    def test_full_resync_when_slot_invalidated(self) -> None:
        from postgres_manager.schema_evolution import SlotHealth
        report = self._base_report()
        report.slot_health = SlotHealth(
            slot_name=TEST_SUBSCRIPTION,
            active=False,
            lag_bytes=0,
            invalidation_reason="wal_removed",
        )
        plan = plan_repair(report, TEST_REPL_USER)
        assert plan.needs_full_resync is True
        resync_steps = [s for s in plan.steps if s.requires_resync]
        assert len(resync_steps) == 1
        assert resync_steps[0].target == "subscriber"
        assert resync_steps[0].phase == 3


# ---------------------------------------------------------------------------
# CLI tests: detect-drift
# ---------------------------------------------------------------------------


class TestDetectDriftCLI:
    def test_detect_drift_writes_json_file(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_table(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB, TEST_TABLE)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )
        out_path = tmp_path / "drift.json"

        result = _invoke(runner, [
            "replication", "detect-drift",
            "--config", str(schema_config_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--output", str(out_path),
        ])

        assert result.exit_code == 0, result.output
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "publisher_instance" in data
        assert "table_drifts" in data

    def test_detect_drift_shows_publisher_and_subscriber_labels(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, []
        )
        out_path = tmp_path / "drift.json"

        result = _invoke(runner, [
            "replication", "detect-drift",
            "--config", str(schema_config_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--output", str(out_path),
        ])

        assert result.exit_code == 0, result.output
        assert "[PUBLISHER]" in result.output
        assert "[SUBSCRIBER]" in result.output

    def test_detect_drift_reports_missing_table(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        # Table missing on subscriber
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )
        out_path = tmp_path / "drift.json"

        result = _invoke(runner, [
            "replication", "detect-drift",
            "--config", str(schema_config_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--output", str(out_path),
        ])

        assert result.exit_code == 0, result.output
        assert "missing on subscriber" in result.output.lower() or "missing_on_subscriber" in result.output

    def test_detect_drift_fails_without_replication_config(
        self, pg_instances: dict[str, object], tmp_path: Path, runner: CliRunner
    ) -> None:
        """Command should exit with error if config has no [replication] section."""
        cfg = tmp_path / "config.toml"
        cfg.write_text(f"""
[postgres]
version = {TEST_PG_VERSION}

[[instances]]
cluster_name = "{TEST_CLUSTER_1}"
port = {TEST_PORT_1}
admin_user = "{TEST_ADMIN_1}"

[database]
name = "{TEST_DB}"

[table]
name = "{TEST_TABLE}"
""")
        result = runner.invoke(main, [
            "replication", "detect-drift",
            "--config", str(cfg),
            "--pub-password", TEST_PASSWORD_1,
            "--output", str(tmp_path / "drift.json"),
        ], catch_exceptions=False)

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI tests: plan-repair
# ---------------------------------------------------------------------------


class TestPlanRepairCLI:
    def test_plan_repair_reads_drift_and_writes_plan(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Build a drift report with one drifted table
        drift_report = DriftReport(
            detected_at="2026-01-01T00:00:00+00:00",
            publisher_instance=TEST_CLUSTER_1,
            subscriber_instance=TEST_CLUSTER_2,
            database=TEST_DB,
            publication_name=TEST_PUBLICATION,
            subscription_name=TEST_SUBSCRIPTION,
            table_drifts=[
                TableDrift(
                    schema="public",
                    table="orders",
                    issues=["new_unconfigured"],
                )
            ],
        )
        drift_path = tmp_path / "drift.json"
        drift_path.write_text(drift_report.to_json())
        plan_path = tmp_path / "plan.json"

        result = _invoke(runner, [
            "replication", "plan-repair",
            "--config", str(schema_config_path),
            "--drift-report", str(drift_path),
            "--output", str(plan_path),
        ])

        assert result.exit_code == 0, result.output
        assert plan_path.exists()
        data = json.loads(plan_path.read_text())
        assert "steps" in data
        assert len(data["steps"]) > 0

    def test_plan_repair_output_labels_publisher_and_subscriber(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        drift_report = DriftReport(
            detected_at="2026-01-01T00:00:00+00:00",
            publisher_instance=TEST_CLUSTER_1,
            subscriber_instance=TEST_CLUSTER_2,
            database=TEST_DB,
            publication_name=TEST_PUBLICATION,
            subscription_name=TEST_SUBSCRIPTION,
            table_drifts=[
                TableDrift(schema="public", table="orders", issues=["new_unconfigured"]),
                TableDrift(schema="public", table="users", issues=["missing_on_subscriber"]),
            ],
        )
        drift_path = tmp_path / "drift.json"
        drift_path.write_text(drift_report.to_json())

        result = _invoke(runner, [
            "replication", "plan-repair",
            "--config", str(schema_config_path),
            "--drift-report", str(drift_path),
            "--output", str(tmp_path / "plan.json"),
        ])

        assert result.exit_code == 0, result.output
        assert "[PUBLISHER]" in result.output
        assert "[SUBSCRIBER]" in result.output

    def test_plan_repair_shows_no_steps_when_clean(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        drift_report = DriftReport(
            detected_at="2026-01-01T00:00:00+00:00",
            publisher_instance=TEST_CLUSTER_1,
            subscriber_instance=TEST_CLUSTER_2,
            database=TEST_DB,
            publication_name=TEST_PUBLICATION,
            subscription_name=TEST_SUBSCRIPTION,
            table_drifts=[],
        )
        drift_path = tmp_path / "drift.json"
        drift_path.write_text(drift_report.to_json())

        result = _invoke(runner, [
            "replication", "plan-repair",
            "--config", str(schema_config_path),
            "--drift-report", str(drift_path),
            "--output", str(tmp_path / "plan.json"),
        ])

        assert result.exit_code == 0, result.output
        assert "No repair steps" in result.output


# ---------------------------------------------------------------------------
# CLI tests: apply-repair (dry-run)
# ---------------------------------------------------------------------------


class TestApplyRepairCLI:
    def _write_plan(self, tmp_path: Path, steps: list[RepairStep]) -> Path:
        plan = RepairPlan(
            generated_at="2026-01-01T00:00:00+00:00",
            publisher_instance=TEST_CLUSTER_1,
            subscriber_instance=TEST_CLUSTER_2,
            database=TEST_DB,
            publication_name=TEST_PUBLICATION,
            subscription_name=TEST_SUBSCRIPTION,
            steps=steps,
        )
        path = tmp_path / "plan.json"
        path.write_text(plan.to_json())
        return path

    def test_dry_run_prints_sql_without_executing(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        plan_path = self._write_plan(tmp_path, [
            RepairStep(
                step=1,
                phase=1,
                target="publisher",
                description="[PUBLISHER] Test step",
                sql=[f"ALTER PUBLICATION {TEST_PUBLICATION} DROP TABLE {TEST_TABLE};"],
                risk="medium",
            )
        ])

        result = _invoke(runner, [
            "replication", "apply-repair",
            "--config", str(schema_config_path),
            "--plan", str(plan_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--dry-run",
        ])

        assert result.exit_code == 0, result.output
        assert "[DRY RUN]" in result.output
        # Verify publication still exists (not modified)
        tables = get_publication_tables(
            _pub_instance(), TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION
        )
        assert ("public", TEST_TABLE) in tables, "Dry run should not have dropped the table"

    def test_apply_repair_shows_publisher_subscriber_labels(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, []
        )

        plan_path = self._write_plan(tmp_path, [
            RepairStep(
                step=1,
                phase=3,
                target="subscriber",
                description="[SUBSCRIBER] Refresh publication",
                sql=["-- Manual: ALTER SUBSCRIPTION ... REFRESH PUBLICATION;"],
                risk="low",
            )
        ])

        result = _invoke(runner, [
            "replication", "apply-repair",
            "--config", str(schema_config_path),
            "--plan", str(plan_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--dry-run",
        ])

        assert result.exit_code == 0, result.output
        assert "[PUBLISHER]" in result.output or "[SUBSCRIBER]" in result.output

    def test_apply_step_option_runs_single_step(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_db(TEST_PORT_2, TEST_ADMIN_2, TEST_PASSWORD_2, TEST_DB)
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, []
        )

        plan_path = self._write_plan(tmp_path, [
            RepairStep(
                step=1, phase=1, target="publisher",
                description="[PUBLISHER] Step 1",
                sql=["-- step 1 comment"],
                risk="low",
            ),
            RepairStep(
                step=2, phase=2, target="subscriber",
                description="[SUBSCRIBER] Step 2",
                sql=["-- step 2 comment"],
                risk="low",
            ),
        ])

        result = _invoke(runner, [
            "replication", "apply-repair",
            "--config", str(schema_config_path),
            "--plan", str(plan_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
            "--step", "1",
            "--dry-run",
        ])

        assert result.exit_code == 0, result.output
        assert "step 1 comment" in result.output.lower() or "Step 1" in result.output
        assert "step 2 comment" not in result.output.lower()

    def test_apply_repair_executes_publisher_sql(
        self, pg_instances: dict[str, object], schema_config_path: Path, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Apply a real ALTER PUBLICATION step on publisher and verify it worked."""
        _create_db(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_TABLE)
        _create_table(TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, "extra_table")
        _create_publication(
            TEST_PORT_1, TEST_ADMIN_1, TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION, [TEST_TABLE]
        )

        plan_path = self._write_plan(tmp_path, [
            RepairStep(
                step=1,
                phase=1,
                target="publisher",
                description=f"[PUBLISHER] Add extra_table to {TEST_PUBLICATION}",
                sql=[f"ALTER PUBLICATION {TEST_PUBLICATION} ADD TABLE extra_table;"],
                risk="low",
            )
        ])

        result = _invoke(runner, [
            "replication", "apply-repair",
            "--config", str(schema_config_path),
            "--plan", str(plan_path),
            "--pub-password", TEST_PASSWORD_1,
            "--sub-password", TEST_PASSWORD_2,
        ])

        assert result.exit_code == 0, result.output
        tables = get_publication_tables(
            _pub_instance(), TEST_PASSWORD_1, TEST_DB, TEST_PUBLICATION
        )
        assert ("public", "extra_table") in tables, (
            "extra_table should now be in the publication"
        )
