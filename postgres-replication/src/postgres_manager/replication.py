"""Logical replication operations: prepare, publish, subscribe, monitor."""

from __future__ import annotations

import subprocess
import sys
import time

import psycopg
from psycopg import errors, sql

from .config import InstanceConfig, ReplicationConfig, TableReplicationEntry


class ReplicationError(Exception):
    """Raised when a replication operation fails."""


# ---------------------------------------------------------------------------
# Connection helpers
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


def _dry(label: str, *lines: str) -> None:
    """Print dry-run SQL/command lines with a consistent header."""
    print(f"\n[DRY RUN] {label}:")
    for line in lines:
        print(f"  {line}")


def _as_int(val: object) -> int:
    """Cast an opaque dict value to int safely."""
    if isinstance(val, int):
        return val
    return int(str(val))


# ---------------------------------------------------------------------------
# Table inspection
# ---------------------------------------------------------------------------


def get_table_columns(
    instance: InstanceConfig,
    password: str,
    db_name: str,
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """Return all user tables and their columns from an instance.

    Args:
        instance: Instance configuration.
        password: Admin password.
        db_name: Database to inspect.

    Returns:
        Dict mapping ``(schema, table)`` to an ordered list of
        ``(column_name, data_type)`` tuples.
    """
    with _tcp_connect(instance, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT t.schemaname, t.tablename, c.column_name, c.data_type
            FROM pg_tables t
            JOIN information_schema.columns c
                ON c.table_schema = t.schemaname
               AND c.table_name  = t.tablename
            WHERE t.schemaname NOT IN
                ('pg_catalog', 'information_schema', 'pg_toast')
              AND t.schemaname NOT LIKE 'pg_%'
            ORDER BY t.schemaname, t.tablename, c.ordinal_position
            """
        ).fetchall()

    result: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for row in rows:
        schema, table = str(row[0]), str(row[1])
        col_name, col_type = str(row[2]), str(row[3])
        key = (schema, table)
        if key not in result:
            result[key] = []
        result[key].append((col_name, col_type))
    return result


def compare_tables(
    publisher_cols: dict[tuple[str, str], list[tuple[str, str]]],
    subscriber_cols: dict[tuple[str, str], list[tuple[str, str]]],
) -> list[TableReplicationEntry]:
    """Compare publisher and subscriber table sets.

    For each table present in the publisher, determine the replication status:

    * ``create``       – table absent from subscriber.
    * ``exists``       – identical column list.
    * ``alter``        – subscriber has a strict subset of publisher columns.
    * ``incompatible`` – subscriber has extra or conflicting columns.

    Args:
        publisher_cols: Output of :func:`get_table_columns` from the publisher.
        subscriber_cols: Output of :func:`get_table_columns` from the subscriber.

    Returns:
        List of :class:`TableReplicationEntry` objects, one per publisher table.
    """
    entries: list[TableReplicationEntry] = []
    for (schema, table), pub_col_list in publisher_cols.items():
        if (schema, table) not in subscriber_cols:
            status = "create"
        else:
            sub_col_list = subscriber_cols[(schema, table)]
            if pub_col_list == sub_col_list:
                status = "exists"
            else:
                pub_names = [c[0] for c in pub_col_list]
                sub_names = [c[0] for c in sub_col_list]
                if all(n in pub_names for n in sub_names):
                    status = "alter"
                else:
                    status = "incompatible"
        entries.append(TableReplicationEntry(schema=schema, name=table, status=status))
    return entries


# ---------------------------------------------------------------------------
# Table DDL
# ---------------------------------------------------------------------------


def get_table_ddl(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    schema: str,
    table: str,
) -> str:
    """Build a ``CREATE TABLE IF NOT EXISTS`` statement from live column metadata.

    Args:
        instance: Instance configuration (the publisher).
        password: Admin password.
        db_name: Database name.
        schema: Table schema.
        table: Table name.

    Returns:
        SQL string ready to execute on the subscriber.
    """
    with _tcp_connect(instance, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.is_nullable,
                EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                       AND tc.table_schema    = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema    = c.table_schema
                      AND tc.table_name      = c.table_name
                      AND kcu.column_name    = c.column_name
                ) AS is_pk
            FROM information_schema.columns c
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
            """,
            (schema, table),
        ).fetchall()

    col_defs: list[str] = []
    pk_cols: list[str] = []

    for col_name, data_type, max_len, is_nullable, is_pk in rows:
        type_str = f"{data_type}({max_len})" if max_len else data_type
        nullable = "" if is_nullable == "YES" else " NOT NULL"
        col_defs.append(f'"{col_name}" {type_str}{nullable}')
        if is_pk:
            pk_cols.append(f'"{col_name}"')

    if pk_cols:
        col_defs.append(f'PRIMARY KEY ({", ".join(pk_cols)})')

    body = ", ".join(col_defs)
    return f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" ({body})'


def create_table_on_subscriber(
    publisher: InstanceConfig,
    pub_password: str,
    subscriber: InstanceConfig,
    sub_password: str,
    db_name: str,
    schema: str,
    table: str,
    dry_run: bool = False,
) -> None:
    """Create a table on the subscriber using DDL derived from the publisher.

    Args:
        publisher: Publisher instance (source of DDL).
        pub_password: Publisher admin password.
        subscriber: Subscriber instance.
        sub_password: Subscriber admin password.
        db_name: Database name (must already exist on subscriber).
        schema: Table schema.
        table: Table name.
        dry_run: If True, print DDL without executing.
    """
    ddl = get_table_ddl(publisher, pub_password, db_name, schema, table)
    if dry_run:
        _dry(
            f"create table on subscriber {subscriber.cluster_name} port {subscriber.port},"
            f" db {db_name}",
            f"{ddl};",
        )
        return
    print(f"  Creating table '{schema}.{table}' on subscriber...")
    with _tcp_connect(subscriber, sub_password, db_name) as conn:
        conn.execute(ddl.encode())


# ---------------------------------------------------------------------------
# wal_level
# ---------------------------------------------------------------------------


def ensure_wal_logical(
    pg_version: int,
    cluster_name: str,
    instance: InstanceConfig,
    password: str,
    dry_run: bool = False,
) -> bool:
    """Ensure ``wal_level = logical`` on a cluster, restarting if needed.

    Args:
        pg_version: PostgreSQL major version.
        cluster_name: Cluster name.
        instance: Instance configuration (used to check current setting).
        password: Admin password.
        dry_run: If True, print commands without executing.

    Returns:
        ``True`` if the cluster was restarted, ``False`` if already logical.
    """
    if dry_run:
        _dry(
            f"ensure wal_level=logical on {cluster_name} port {instance.port}",
            "-- Check current setting:",
            "SHOW wal_level;",
            "-- If not already logical:",
            "ALTER SYSTEM SET wal_level = 'logical';",
            f"-- pg_ctlcluster {pg_version} {cluster_name} restart",
        )
        return False

    with _tcp_connect(instance, password) as conn:
        row = conn.execute("SHOW wal_level").fetchone()
        current = str(row[0]) if row else ""

    if current == "logical":
        print(f"  wal_level is already 'logical' on '{cluster_name}'.")
        return False

    print(f"  Setting wal_level = logical on '{cluster_name}' (requires restart)...")
    with _tcp_connect(instance, password) as conn:
        conn.execute("ALTER SYSTEM SET wal_level = 'logical'")

    subprocess.run(
        ["pg_ctlcluster", str(pg_version), cluster_name, "restart"],
        check=True,
        capture_output=True,
        text=True,
    )
    time.sleep(3)
    print(f"  Cluster '{cluster_name}' restarted with wal_level = logical.")
    return True


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


def create_replication_user(
    instance: InstanceConfig,
    password: str,
    replication_user: str,
    replication_password: str,
    db_name: str,
    tables: list[tuple[str, str]],
    dry_run: bool = False,
) -> None:
    """Create (or update) a replication role and grant required privileges.

    Args:
        instance: Publisher instance.
        password: Admin password.
        replication_user: Name of the role to create.
        replication_password: Password for the replication role.
        db_name: Database where tables live.
        tables: List of ``(schema, table)`` pairs to grant SELECT on.
        dry_run: If True, print SQL without executing.
    """
    if dry_run:
        grant_lines = [
            f'GRANT CONNECT ON DATABASE "{db_name}" TO "{replication_user}";',
        ] + [
            f'GRANT SELECT ON "{s}"."{t}" TO "{replication_user}";'
            for s, t in tables
        ]
        _dry(
            f"create replication user on {instance.cluster_name} port {instance.port}",
            f'CREATE ROLE "{replication_user}" WITH LOGIN REPLICATION PASSWORD \'***\';',
            "-- or if role already exists:",
            f'ALTER ROLE "{replication_user}" WITH LOGIN REPLICATION PASSWORD \'***\';',
            *grant_lines,
        )
        return

    role_ident = sql.Identifier(replication_user)
    pw_literal = sql.Literal(replication_password)

    with _tcp_connect(instance, password) as conn:
        try:
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN REPLICATION PASSWORD {}"
                ).format(role_ident, pw_literal)
            )
        except errors.DuplicateObject:
            conn.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN REPLICATION PASSWORD {}"
                ).format(role_ident, pw_literal)
            )

    with _tcp_connect(instance, password, db_name) as conn:
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(db_name), role_ident
            )
        )
        for schema, table in tables:
            conn.execute(
                sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    role_ident,
                )
            )

    print(f"  Replication user '{replication_user}' configured.")


def setup_publication(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    publication_name: str,
    tables: list[tuple[str, str]],
    dry_run: bool = False,
) -> None:
    """Drop-and-recreate a publication for the specified tables.

    Args:
        instance: Publisher instance.
        password: Admin password.
        db_name: Database name.
        publication_name: Publication name.
        tables: List of ``(schema, table)`` pairs to publish.
        dry_run: If True, print SQL without executing.
    """
    table_refs = ", ".join(f'"{s}"."{t}"' for s, t in tables)
    if dry_run:
        _dry(
            f"setup publication on {instance.cluster_name} port {instance.port}, db {db_name}",
            f'DROP PUBLICATION IF EXISTS "{publication_name}";',
            f'CREATE PUBLICATION "{publication_name}" FOR TABLE {table_refs};',
        )
        return

    pub_ident = sql.Identifier(publication_name)
    table_parts = [
        sql.SQL("{}.{}").format(sql.Identifier(s), sql.Identifier(t))
        for s, t in tables
    ]
    table_list = sql.SQL(", ").join(table_parts)

    with _tcp_connect(instance, password, db_name) as conn:
        conn.execute(sql.SQL("DROP PUBLICATION IF EXISTS {}").format(pub_ident))
        conn.execute(
            sql.SQL("CREATE PUBLICATION {} FOR TABLE {}").format(pub_ident, table_list)
        )

    print(
        f"  Publication '{publication_name}' created for "
        f"{len(tables)} table(s): "
        f"{', '.join(f'{s}.{t}' for s, t in tables)}."
    )


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


def setup_subscription(
    subscriber: InstanceConfig,
    sub_password: str,
    db_name: str,
    subscription_name: str,
    publisher_host: str,
    publisher_port: int,
    replication_user: str,
    replication_password: str,
    publication_name: str,
    dry_run: bool = False,
) -> None:
    """Drop-and-recreate a subscription on the subscriber.

    Args:
        subscriber: Subscriber instance.
        sub_password: Subscriber admin password.
        db_name: Database name.
        subscription_name: Subscription name.
        publisher_host: Host to connect to the publisher on.
        publisher_port: Publisher TCP port.
        replication_user: Replication user name.
        replication_password: Replication user password.
        publication_name: Name of the publication on the publisher.
        dry_run: If True, print SQL without executing.
    """
    connstr = (
        f"host={publisher_host} "
        f"port={publisher_port} "
        f"user={replication_user} "
        f"password=*** "
        f"dbname={db_name}"
    )
    if dry_run:
        _dry(
            f"setup subscription on {subscriber.cluster_name} port {subscriber.port},"
            f" db {db_name}",
            f'DROP SUBSCRIPTION IF EXISTS "{subscription_name}";',
            f'CREATE SUBSCRIPTION "{subscription_name}"',
            f"    CONNECTION '{connstr}'",
            f'    PUBLICATION "{publication_name}";',
        )
        return

    real_connstr = (
        f"host={publisher_host} "
        f"port={publisher_port} "
        f"user={replication_user} "
        f"password={replication_password} "
        f"dbname={db_name}"
    )
    sub_ident = sql.Identifier(subscription_name)

    with _tcp_connect(subscriber, sub_password, db_name) as conn:
        conn.execute(
            sql.SQL("DROP SUBSCRIPTION IF EXISTS {}").format(sub_ident)
        )
        conn.execute(
            sql.SQL(
                "CREATE SUBSCRIPTION {} CONNECTION {} PUBLICATION {}"
            ).format(
                sub_ident,
                sql.Literal(real_connstr),
                sql.Identifier(publication_name),
            )
        )

    print(f"  Subscription '{subscription_name}' created.")


# ---------------------------------------------------------------------------
# Monitor: stats
# ---------------------------------------------------------------------------


def get_replication_stats(
    publisher: InstanceConfig,
    password: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return streaming replication stats and logical slot info from the publisher.

    Args:
        publisher: Publisher instance.
        password: Admin password.

    Returns:
        Tuple of ``(connections, slots)`` where each entry is a dict.
    """
    with _tcp_connect(publisher, password) as conn:
        stat_rows = conn.execute(
            """
            SELECT
                application_name,
                client_addr::text,
                state,
                sent_lsn::text,
                write_lsn::text,
                flush_lsn::text,
                replay_lsn::text,
                write_lag::text,
                flush_lag::text,
                replay_lag::text,
                sync_state
            FROM pg_stat_replication
            ORDER BY application_name
            """
        ).fetchall()
        stat_cols = [
            "application_name", "client_addr", "state",
            "sent_lsn", "write_lsn", "flush_lsn", "replay_lsn",
            "write_lag", "flush_lag", "replay_lag", "sync_state",
        ]
        connections = [dict(zip(stat_cols, row)) for row in stat_rows]

        slot_rows = conn.execute(
            """
            SELECT
                slot_name,
                slot_type,
                active,
                pg_size_pretty(
                    pg_wal_lsn_diff(
                        pg_current_wal_lsn(),
                        confirmed_flush_lsn
                    )
                ) AS lag_pretty,
                GREATEST(
                    pg_wal_lsn_diff(
                        pg_current_wal_lsn(),
                        confirmed_flush_lsn
                    ), 0
                ) AS lag_bytes
            FROM pg_replication_slots
            WHERE slot_type = 'logical'
            ORDER BY slot_name
            """
        ).fetchall()
        slot_cols = ["slot_name", "slot_type", "active", "lag_pretty", "lag_bytes"]
        slots = [dict(zip(slot_cols, row)) for row in slot_rows]

    return connections, slots


# ---------------------------------------------------------------------------
# Monitor: row counts
# ---------------------------------------------------------------------------


def get_row_counts(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    tables: list[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    """Count rows in each table.

    Returns -1 for tables that cannot be counted (e.g. table doesn't exist yet).

    Args:
        instance: Instance configuration.
        password: Admin password.
        db_name: Database name.
        tables: List of ``(schema, table)`` tuples.

    Returns:
        Dict mapping ``(schema, table)`` to row count (or -1 on error).
    """
    counts: dict[tuple[str, str], int] = {}
    with _tcp_connect(instance, password, db_name) as conn:
        for schema, table in tables:
            try:
                row = conn.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                ).fetchone()
                counts[(schema, table)] = _as_int(row[0]) if row else 0
            except Exception:
                counts[(schema, table)] = -1
    return counts


def get_pk_columns(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    schema: str,
    table: str,
) -> list[str]:
    """Return primary key column names for a table.

    Args:
        instance: Instance configuration.
        password: Admin password.
        db_name: Database name.
        schema: Table schema.
        table: Table name.

    Returns:
        Ordered list of primary key column names.
    """
    with _tcp_connect(instance, password, db_name) as conn:
        rows = conn.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema    = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema    = %s
              AND tc.table_name      = %s
            ORDER BY kcu.ordinal_position
            """,
            (schema, table),
        ).fetchall()
    return [str(row[0]) for row in rows]


def get_max_pk_values(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    schema: str,
    table: str,
    pk_cols: list[str],
) -> dict[str, object]:
    """Get the maximum value of each primary key column.

    Args:
        instance: Instance configuration.
        password: Admin password.
        db_name: Database name.
        schema: Table schema.
        table: Table name.
        pk_cols: Primary key column names.

    Returns:
        Dict mapping column name to its maximum value (or None).
    """
    if not pk_cols:
        return {}
    result: dict[str, object] = {}
    with _tcp_connect(instance, password, db_name) as conn:
        for col in pk_cols:
            try:
                row = conn.execute(
                    sql.SQL("SELECT MAX({}) FROM {}.{}").format(
                        sql.Identifier(col),
                        sql.Identifier(schema),
                        sql.Identifier(table),
                    )
                ).fetchone()
                result[col] = row[0] if row else None
            except Exception:
                result[col] = None
    return result


# ---------------------------------------------------------------------------
# Polling: wait for replication to catch up
# ---------------------------------------------------------------------------


def _format_bytes(n: int) -> str:
    """Human-readable byte size."""
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def _format_rate(rate: float) -> str:
    """Human-readable bytes-per-second rate."""
    if rate >= 1024 * 1024:
        return f"{rate / 1024 / 1024:.1f} MB/s"
    if rate >= 1024:
        return f"{rate / 1024:.1f} KB/s"
    return f"{rate:.0f} B/s"


def _format_eta(eta_secs: float) -> str:
    """Human-readable estimated time."""
    if eta_secs < 60:
        return f"~{eta_secs:.0f}s"
    if eta_secs < 3600:
        return f"~{eta_secs / 60:.1f}m"
    return f"~{eta_secs / 3600:.1f}h"


def poll_until_caught_up(
    publisher: InstanceConfig,
    password: str,
    max_seconds: int = 30,
    poll_interval: float = 2.0,
) -> None:
    """Poll replication lag every ``poll_interval`` seconds until caught up or timeout.

    Prints a progress line on each poll showing bytes remaining, estimated
    throughput, and estimated time to completion.  Stops when lag reaches zero
    or ``max_seconds`` elapses.

    Args:
        publisher: Publisher instance to query.
        password: Publisher admin password.
        max_seconds: Maximum seconds to wait.
        poll_interval: Seconds between polls.
    """
    _, slots = get_replication_stats(publisher, password)
    if not slots:
        print("  No logical replication slots found.")
        return

    total_lag = sum(_as_int(s["lag_bytes"]) for s in slots)
    if total_lag == 0:
        print("  Replication is already caught up (0 bytes lag).")
        return

    print(f"\n  Monitoring replication catch-up (up to {max_seconds}s)...")
    print(f"  Initial lag: {_format_bytes(total_lag)}")
    print(f"  {'Elapsed':>7}  {'Remaining':>12}  {'Rate':>12}  {'ETA':>10}  Status")
    print(f"  {'-'*7}  {'-'*12}  {'-'*12}  {'-'*10}  ------")

    start = time.monotonic()
    prev_lag = total_lag
    prev_time = start

    while True:
        time.sleep(poll_interval)

        elapsed = time.monotonic() - start
        _, slots = get_replication_stats(publisher, password)
        total_lag = sum(_as_int(s["lag_bytes"]) for s in slots)
        now = time.monotonic()
        dt = now - prev_time
        delta_bytes = prev_lag - total_lag

        if delta_bytes > 0 and dt > 0:
            rate = delta_bytes / dt
            eta_str = _format_eta(total_lag / rate) if total_lag > 0 else "done"
            rate_str = _format_rate(rate)
        else:
            rate_str = "0 B/s"
            eta_str = "done" if total_lag == 0 else "unknown"

        active = any(s["active"] for s in slots)
        status = "active" if active else "INACTIVE"
        remaining_str = _format_bytes(total_lag) if total_lag > 0 else "0 B"

        print(
            f"  {elapsed:>6.0f}s  {remaining_str:>12}  {rate_str:>12}"
            f"  {eta_str:>10}  {status}"
        )
        sys.stdout.flush()

        prev_lag = total_lag
        prev_time = now

        if total_lag == 0:
            print("  Replication fully caught up!")
            break

        if elapsed >= max_seconds:
            print(
                f"  Monitoring stopped after {max_seconds}s."
                f" Remaining lag: {_format_bytes(total_lag)}"
            )
            break
