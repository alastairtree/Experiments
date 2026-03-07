"""Schema evolution: detect drift, plan repair, apply repair for logical replication."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg

from .config import InstanceConfig, ReplicationConfig


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ColumnDiff:
    """A column-level difference between publisher and subscriber."""

    name: str
    # "missing_on_subscriber" | "missing_on_publisher" | "type_mismatch" | "possible_rename"
    issue: str
    publisher_type: str | None = None
    subscriber_type: str | None = None
    suggestion: str | None = None


@dataclass
class TableDrift:
    """Drift detected for a single table."""

    schema: str
    table: str
    # "new_unconfigured"         – exists on publisher, not in publication
    # "dropped_from_publisher"   – in publication config, gone from publisher DB
    # "missing_on_subscriber"    – in publication, not yet on subscriber
    # "schema_changed"           – exists on both but columns differ
    # "no_replica_identity"      – table has no PK / REPLICA IDENTITY set
    issues: list[str]
    column_diffs: list[ColumnDiff] = field(default_factory=list)
    has_replica_identity: bool = True


@dataclass
class SlotHealth:
    """Health of a replication slot."""

    slot_name: str
    active: bool
    lag_bytes: int
    invalidation_reason: str | None = None


@dataclass
class DriftReport:
    """Full drift report between publisher and subscriber."""

    detected_at: str
    publisher_instance: str
    subscriber_instance: str
    database: str
    publication_name: str
    subscription_name: str
    table_drifts: list[TableDrift]
    slot_health: SlotHealth | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "DriftReport":
        data: dict[str, Any] = json.loads(text)
        drifts: list[TableDrift] = [
            TableDrift(
                schema=str(d["schema"]),
                table=str(d["table"]),
                issues=list(d["issues"]),
                column_diffs=[
                    ColumnDiff(
                        name=str(c["name"]),
                        issue=str(c["issue"]),
                        publisher_type=c.get("publisher_type"),
                        subscriber_type=c.get("subscriber_type"),
                        suggestion=c.get("suggestion"),
                    )
                    for c in d.get("column_diffs", [])
                ],
                has_replica_identity=bool(d.get("has_replica_identity", True)),
            )
            for d in data["table_drifts"]
        ]
        raw_slot = data.get("slot_health")
        slot: SlotHealth | None = (
            SlotHealth(
                slot_name=str(raw_slot["slot_name"]),
                active=bool(raw_slot["active"]),
                lag_bytes=int(raw_slot["lag_bytes"]),
                invalidation_reason=raw_slot.get("invalidation_reason"),
            )
            if raw_slot
            else None
        )
        return cls(
            detected_at=str(data["detected_at"]),
            publisher_instance=str(data["publisher_instance"]),
            subscriber_instance=str(data["subscriber_instance"]),
            database=str(data["database"]),
            publication_name=str(data["publication_name"]),
            subscription_name=str(data["subscription_name"]),
            table_drifts=drifts,
            slot_health=slot,
        )


@dataclass
class RepairStep:
    """A single ordered step in a repair plan."""

    step: int
    phase: int
    target: str  # "publisher" | "subscriber"
    description: str
    sql: list[str]
    risk: str  # "low" | "medium" | "high"
    requires_resync: bool = False
    manual_review: bool = False


@dataclass
class RepairPlan:
    """Ordered repair plan generated from a drift report."""

    generated_at: str
    publisher_instance: str
    subscriber_instance: str
    database: str
    publication_name: str
    subscription_name: str
    needs_full_resync: bool = False
    steps: list[RepairStep] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "RepairPlan":
        data: dict[str, Any] = json.loads(text)
        steps = [
            RepairStep(
                step=int(s["step"]),
                phase=int(s["phase"]),
                target=str(s["target"]),
                description=str(s["description"]),
                sql=list(s["sql"]),
                risk=str(s["risk"]),
                requires_resync=bool(s.get("requires_resync", False)),
                manual_review=bool(s.get("manual_review", False)),
            )
            for s in data["steps"]
        ]
        return cls(
            generated_at=str(data["generated_at"]),
            publisher_instance=str(data["publisher_instance"]),
            subscriber_instance=str(data["subscriber_instance"]),
            database=str(data["database"]),
            publication_name=str(data["publication_name"]),
            subscription_name=str(data["subscription_name"]),
            needs_full_resync=bool(data.get("needs_full_resync", False)),
            steps=steps,
        )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _tcp_connect(
    instance: InstanceConfig,
    password: str,
    database: str = "postgres",
) -> psycopg.Connection[tuple[object, ...]]:
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost",
        port=instance.port,
        user=instance.admin_user,
        password=password,
        dbname=database,
        autocommit=True,
    )
    return conn


def get_publication_tables(
    publisher: InstanceConfig,
    password: str,
    db_name: str,
    publication_name: str,
) -> list[tuple[str, str]]:
    """Return (schema, table) pairs that are part of the publication."""
    with _tcp_connect(publisher, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT schemaname, tablename
            FROM pg_publication_tables
            WHERE pubname = %s
            ORDER BY schemaname, tablename
            """,
            (publication_name,),
        ).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


def get_all_user_tables(
    instance: InstanceConfig,
    password: str,
    db_name: str,
) -> list[tuple[str, str]]:
    """Return (schema, table) pairs for all user tables in the database."""
    with _tcp_connect(instance, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
            """,
        ).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


def get_table_columns(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    schema: str,
    table: str,
) -> dict[str, str]:
    """Return {column_name: data_type} for the given table."""
    with _tcp_connect(instance, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def get_replica_identity(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    schema: str,
    table: str,
) -> str:
    """Return the replica identity character: 'd','n','f','i'."""
    with _tcp_connect(instance, password, db_name) as conn:
        row = conn.execute(
            """
            SELECT c.relreplident
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        ).fetchone()
    if row is None:
        return "n"
    return str(row[0])


def get_slot_health(
    publisher: InstanceConfig,
    password: str,
    subscription_name: str,
) -> SlotHealth | None:
    """Return slot health for the named subscription slot, or None if not found.

    Uses ``wal_status`` (available since PG 13) to detect slot invalidation
    instead of ``invalidation_reason`` which was added in PG 17.
    """
    slot_name = subscription_name
    with _tcp_connect(publisher, password) as conn:
        row = conn.execute(
            """
            SELECT slot_name, active,
                   pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes,
                   wal_status
            FROM pg_replication_slots
            WHERE slot_name = %s
            """,
            (slot_name,),
        ).fetchone()
    if row is None:
        return None
    wal_status = str(row[3]) if row[3] is not None else None
    # wal_status = 'lost' means the slot was invalidated (WAL was removed)
    invalidation_reason = "wal_removed" if wal_status == "lost" else None
    return SlotHealth(
        slot_name=str(row[0]),
        active=bool(row[1]),
        lag_bytes=max(0, int(str(row[2]))),
        invalidation_reason=invalidation_reason,
    )


def _compare_columns(
    pub_cols: dict[str, str],
    sub_cols: dict[str, str],
    schema: str,
    table: str,
) -> list[ColumnDiff]:
    """Compare columns between publisher and subscriber, returning diffs."""
    diffs: list[ColumnDiff] = []

    for col, dtype in pub_cols.items():
        if col not in sub_cols:
            diffs.append(
                ColumnDiff(
                    name=col,
                    issue="missing_on_subscriber",
                    publisher_type=dtype,
                    suggestion=f"ALTER TABLE {schema}.{table} ADD COLUMN {col} {dtype};",
                )
            )
        elif sub_cols[col] != dtype:
            diffs.append(
                ColumnDiff(
                    name=col,
                    issue="type_mismatch",
                    publisher_type=dtype,
                    subscriber_type=sub_cols[col],
                    suggestion=(
                        f"ALTER TABLE {schema}.{table} ALTER COLUMN {col} "
                        f"TYPE {dtype};  -- review carefully"
                    ),
                )
            )

    for col, dtype in sub_cols.items():
        if col not in pub_cols:
            diffs.append(
                ColumnDiff(
                    name=col,
                    issue="missing_on_publisher",
                    subscriber_type=dtype,
                    suggestion=(
                        f"-- Column '{col}' only on subscriber. "
                        "Check for rename or manual addition."
                    ),
                )
            )

    return diffs


# ---------------------------------------------------------------------------
# detect_drift
# ---------------------------------------------------------------------------


def detect_drift(
    publisher: InstanceConfig,
    pub_password: str,
    subscriber: InstanceConfig,
    sub_password: str,
    repl: ReplicationConfig,
    db_name: str,
) -> DriftReport:
    """Compare publisher and subscriber states, returning a DriftReport.

    Detects:
    - Tables on publisher not in publication ("new_unconfigured")
    - Tables in publication missing from publisher DB ("dropped_from_publisher")
    - Tables in publication missing from subscriber ("missing_on_subscriber")
    - Column differences for tables that exist on both sides ("schema_changed")
    - Tables without replica identity ("no_replica_identity")
    - Slot health (lag, active, invalidation)
    """
    pub_tables_in_db = set(get_all_user_tables(publisher, pub_password, db_name))
    pub_tables_in_pub = set(get_publication_tables(publisher, pub_password, db_name, repl.publication_name))
    sub_tables_in_db = set(get_all_user_tables(subscriber, sub_password, db_name))

    drifts: list[TableDrift] = []

    # Tables on publisher that are not in the publication
    for schema, table in sorted(pub_tables_in_db - pub_tables_in_pub):
        drifts.append(TableDrift(
            schema=schema,
            table=table,
            issues=["new_unconfigured"],
        ))

    # Tables in publication that have been dropped from the publisher DB
    for schema, table in sorted(pub_tables_in_pub - pub_tables_in_db):
        drifts.append(TableDrift(
            schema=schema,
            table=table,
            issues=["dropped_from_publisher"],
        ))

    # For tables in the publication that still exist on publisher: compare with subscriber
    for schema, table in sorted(pub_tables_in_pub & pub_tables_in_db):
        issues: list[str] = []
        col_diffs: list[ColumnDiff] = []
        has_ri = True

        # Missing on subscriber?
        if (schema, table) not in sub_tables_in_db:
            issues.append("missing_on_subscriber")
        else:
            # Compare columns
            pub_cols = get_table_columns(publisher, pub_password, db_name, schema, table)
            sub_cols = get_table_columns(subscriber, sub_password, db_name, schema, table)
            col_diffs = _compare_columns(pub_cols, sub_cols, schema, table)
            if col_diffs:
                issues.append("schema_changed")

        # Replica identity check (on publisher)
        ri = get_replica_identity(publisher, pub_password, db_name, schema, table)
        if ri == "n":
            issues.append("no_replica_identity")
            has_ri = False

        if issues or col_diffs:
            drifts.append(TableDrift(
                schema=schema,
                table=table,
                issues=issues,
                column_diffs=col_diffs,
                has_replica_identity=has_ri,
            ))

    slot_health = get_slot_health(publisher, pub_password, repl.subscription_name)

    return DriftReport(
        detected_at=datetime.now(timezone.utc).isoformat(),
        publisher_instance=publisher.cluster_name,
        subscriber_instance=subscriber.cluster_name,
        database=db_name,
        publication_name=repl.publication_name,
        subscription_name=repl.subscription_name,
        table_drifts=drifts,
        slot_health=slot_health,
    )


# ---------------------------------------------------------------------------
# plan_repair
# ---------------------------------------------------------------------------


def plan_repair(report: DriftReport, replication_user: str) -> RepairPlan:
    """Generate an ordered RepairPlan from a DriftReport.

    Phase ordering:
      Phase 1 (publisher): Remove dropped tables from publication
      Phase 2 (subscriber): CREATE/ALTER TABLE for missing/changed columns
      Phase 1 (publisher): GRANT SELECT + ADD TABLE to publication for new tables
      Phase 3 (subscriber): REFRESH PUBLICATION (or full resync hint)
    """
    steps: list[RepairStep] = []
    step_num = 0
    needs_full_resync = False

    if report.slot_health and report.slot_health.invalidation_reason:
        needs_full_resync = True

    def next_step() -> int:
        nonlocal step_num
        step_num += 1
        return step_num

    # Phase 1a (publisher): remove dropped tables from publication
    dropped = [d for d in report.table_drifts if "dropped_from_publisher" in d.issues]
    for drift in dropped:
        fqn = f"{drift.schema}.{drift.table}"
        steps.append(RepairStep(
            step=next_step(),
            phase=1,
            target="publisher",
            description=(
                f"[PUBLISHER] Remove dropped table '{fqn}' from publication "
                f"'{report.publication_name}'"
            ),
            sql=[
                f"ALTER PUBLICATION {report.publication_name} DROP TABLE {fqn};",
                f"-- Subscriber: consider dropping or archiving table {fqn} if no longer needed.",
            ],
            risk="medium",
        ))

    # Phase 2 (subscriber): create missing tables and fix schema
    missing = [d for d in report.table_drifts if "missing_on_subscriber" in d.issues]
    for drift in missing:
        fqn = f"{drift.schema}.{drift.table}"
        steps.append(RepairStep(
            step=next_step(),
            phase=2,
            target="subscriber",
            description=(
                f"[SUBSCRIBER] Create missing table '{fqn}' on subscriber "
                f"(copy DDL from publisher)"
            ),
            sql=[
                f"-- Run on subscriber: pg_dump -t {fqn} --schema-only <publisher_connstr>",
                f"-- Then apply the DDL to subscriber database '{report.database}'.",
            ],
            risk="low",
        ))

    schema_changed = [d for d in report.table_drifts if "schema_changed" in d.issues]
    for drift in schema_changed:
        fqn = f"{drift.schema}.{drift.table}"
        sub_sqls: list[str] = []
        has_high_risk = False
        for cd in drift.column_diffs:
            if cd.issue == "missing_on_subscriber" and cd.suggestion:
                sub_sqls.append(cd.suggestion)
            elif cd.issue == "type_mismatch" and cd.suggestion:
                sub_sqls.append(cd.suggestion)
                has_high_risk = True
            elif cd.issue == "missing_on_publisher" and cd.suggestion:
                sub_sqls.append(cd.suggestion)
        if sub_sqls:
            steps.append(RepairStep(
                step=next_step(),
                phase=2,
                target="subscriber",
                description=(
                    f"[SUBSCRIBER] Apply schema changes to '{fqn}' on subscriber"
                ),
                sql=sub_sqls,
                risk="high" if has_high_risk else "medium",
                manual_review=has_high_risk,
            ))

    # Phase 1b (publisher): add new tables to publication
    new_unconfigured = [d for d in report.table_drifts if "new_unconfigured" in d.issues]
    for drift in new_unconfigured:
        fqn = f"{drift.schema}.{drift.table}"
        ri_sql: list[str] = []
        if not drift.has_replica_identity:
            ri_sql.append(f"ALTER TABLE {fqn} REPLICA IDENTITY FULL;")
        ri_sql += [
            f"GRANT SELECT ON {fqn} TO {replication_user};",
            f"ALTER PUBLICATION {report.publication_name} ADD TABLE {fqn};",
        ]
        steps.append(RepairStep(
            step=next_step(),
            phase=1,
            target="publisher",
            description=(
                f"[PUBLISHER] Add new table '{fqn}' to publication '{report.publication_name}'"
            ),
            sql=ri_sql,
            risk="low",
        ))

    # No-replica-identity tables not already covered
    no_ri = [
        d for d in report.table_drifts
        if "no_replica_identity" in d.issues and "new_unconfigured" not in d.issues
    ]
    for drift in no_ri:
        fqn = f"{drift.schema}.{drift.table}"
        steps.append(RepairStep(
            step=next_step(),
            phase=1,
            target="publisher",
            description=(
                f"[PUBLISHER] Set REPLICA IDENTITY on '{fqn}' (currently NOTHING)"
            ),
            sql=[f"ALTER TABLE {fqn} REPLICA IDENTITY FULL;  -- or add a PK"],
            risk="medium",
            manual_review=True,
        ))

    # Phase 3 (subscriber): refresh publication or full resync hint
    has_new_tables = bool(new_unconfigured or missing)
    if needs_full_resync:
        steps.append(RepairStep(
            step=next_step(),
            phase=3,
            target="subscriber",
            description=(
                f"[SUBSCRIBER] Replication slot was invalidated — full resync required. "
                f"Drop and recreate subscription '{report.subscription_name}'"
            ),
            sql=[
                f"DROP SUBSCRIPTION {report.subscription_name};",
                f"-- Recreate with: postgres-manager replication setup-subscriber ...",
            ],
            risk="high",
            requires_resync=True,
            manual_review=True,
        ))
    elif has_new_tables or schema_changed:
        steps.append(RepairStep(
            step=next_step(),
            phase=3,
            target="subscriber",
            description=(
                f"[SUBSCRIBER] Refresh subscription '{report.subscription_name}' "
                "to pick up publication changes"
            ),
            sql=[
                f"ALTER SUBSCRIPTION {report.subscription_name} REFRESH PUBLICATION;",
            ],
            risk="low",
        ))

    return RepairPlan(
        generated_at=datetime.now(timezone.utc).isoformat(),
        publisher_instance=report.publisher_instance,
        subscriber_instance=report.subscriber_instance,
        database=report.database,
        publication_name=report.publication_name,
        subscription_name=report.subscription_name,
        needs_full_resync=needs_full_resync,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# apply_repair
# ---------------------------------------------------------------------------


def apply_repair_step(
    step: RepairStep,
    publisher: InstanceConfig,
    pub_password: str,
    subscriber: InstanceConfig,
    sub_password: str,
    db_name: str,
    dry_run: bool = False,
) -> None:
    """Execute or preview a single RepairStep.

    Args:
        step: The step to apply.
        publisher: Publisher instance config.
        pub_password: Publisher admin password.
        subscriber: Subscriber instance config.
        sub_password: Subscriber admin password.
        db_name: Database name.
        dry_run: If True, print SQL without executing.
    """
    target_label = step.target.upper()
    print(f"\n[Step {step.step}] Phase {step.phase} | Target: [{target_label}]")
    print(f"  {step.description}")

    if step.manual_review:
        print("  *** MANUAL REVIEW REQUIRED ***")

    executable_sql = [s for s in step.sql if not s.strip().startswith("--")]
    comment_lines = [s for s in step.sql if s.strip().startswith("--")]

    for comment in comment_lines:
        print(f"  {comment}")

    if not executable_sql:
        if dry_run:
            print("  [DRY RUN] No executable SQL for this step (manual action required).")
        else:
            print("  No executable SQL — manual action required (see comments above).")
        return

    if dry_run:
        print(f"  [DRY RUN] Would execute on [{target_label}]:")
        for stmt in executable_sql:
            print(f"    {stmt}")
        return

    # Execute
    instance = publisher if step.target == "publisher" else subscriber
    password = pub_password if step.target == "publisher" else sub_password

    with _tcp_connect(instance, password, db_name) as conn:
        for stmt in executable_sql:
            print(f"  Executing on [{target_label}]: {stmt[:80]}{'...' if len(stmt) > 80 else ''}")
            conn.execute(stmt.encode())

    print(f"  Step {step.step} complete.")
