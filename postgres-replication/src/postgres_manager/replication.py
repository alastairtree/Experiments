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

    Fetches column types, nullability, and primary-key membership from
    ``information_schema`` and constructs a portable DDL string.

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
    """
    ddl = get_table_ddl(publisher, pub_password, db_name, schema, table)
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
) -> bool:
    """Ensure ``wal_level = logical`` on a cluster, restarting if needed.

    Args:
        pg_version: PostgreSQL major version.
        cluster_name: Cluster name.
        instance: Instance configuration (used to check current setting).
        password: Admin password.

    Returns:
        ``True`` if the cluster was restarted, ``False`` if already logical.
    """
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
) -> None:
    """Create (or update) a replication role and grant required privileges.

    Args:
        instance: Publisher instance.
        password: Admin password.
        replication_user: Name of the role to create.
        replication_password: Password for the replication role.
        db_name: Database where tables live.
        tables: List of ``(schema, table)`` pairs to grant SELECT on.
    """
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
) -> None:
    """Drop-and-recreate a publication for the specified tables.

    Args:
        instance: Publisher instance.
        password: Admin password.
        db_name: Database name.
        publication_name: Publication name.
        tables: List of ``(schema, table)`` pairs to publish.
    """
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
    """
    sub_ident = sql.Identifier(subscription_name)
    connstr = (
        f"host={publisher_host} "
        f"port={publisher_port} "
        f"user={replication_user} "
        f"password={replication_password} "
        f"dbname={db_name}"
    )

    with _tcp_connect(subscriber, sub_password, db_name) as conn:
        # DROP first; autocommit=True so each statement is its own txn
        conn.execute(
            sql.SQL("DROP SUBSCRIPTION IF EXISTS {}").format(sub_ident)
        )
        conn.execute(
            sql.SQL(
                "CREATE SUBSCRIPTION {} CONNECTION {} PUBLICATION {}"
            ).format(
                sub_ident,
                sql.Literal(connstr),
                sql.Identifier(publication_name),
            )
        )

    print(f"  Subscription '{subscription_name}' created.")


# ---------------------------------------------------------------------------
# Monitor
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
