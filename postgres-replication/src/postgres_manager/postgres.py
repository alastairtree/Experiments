"""PostgreSQL operations: install, start, create, insert, query."""

from __future__ import annotations

import sys
import subprocess
import time
from pathlib import Path

import psycopg
from psycopg import errors, sql

from .config import AppConfig, InstanceConfig


class PostgresError(Exception):
    """Raised when a PostgreSQL operation fails."""


def _run(
    cmd: list[str],
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command, printing it first.

    Args:
        cmd: Command and arguments.
        check: Whether to raise on non-zero exit.
        capture: Whether to capture stdout/stderr.

    Returns:
        CompletedProcess result.
    """
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def add_pgdg_repo() -> None:
    """Add the PostgreSQL PGDG apt repository for Ubuntu."""
    print("Adding PostgreSQL PGDG apt repository...")
    sources_file = Path("/etc/apt/sources.list.d/pgdg.list")
    if sources_file.exists():
        print("  PGDG repository already configured.")
        return

    # Install prerequisites
    _run(["apt-get", "install", "-y", "curl", "gnupg", "lsb-release"])

    # Download the PGDG signing key
    key_result = _run(
        ["curl", "-fsSL", "https://www.postgresql.org/media/keys/ACCC4CF8.asc"],
        capture=True,
    )
    subprocess.run(
        ["gpg", "--dearmor", "-o", "/etc/apt/trusted.gpg.d/postgresql.gpg"],
        input=key_result.stdout,
        text=True,
        check=True,
    )

    # Detect Ubuntu codename
    codename_result = _run(["lsb_release", "-cs"], capture=True)
    codename = codename_result.stdout.strip()

    # Write sources file
    sources_file.write_text(
        f"deb https://apt.postgresql.org/pub/repos/apt {codename}-pgdg main\n"
    )
    print(f"  Added PGDG repository for {codename}.")


def install_postgres(pg_version: int) -> None:
    """Install PostgreSQL binaries via apt.

    Args:
        pg_version: PostgreSQL major version to install (e.g. 18).
    """
    print(f"Installing PostgreSQL {pg_version}...")
    _run(["apt-get", "update", "-qq"])
    _run([
        "apt-get", "install", "-y",
        f"postgresql-{pg_version}",
        "postgresql-common",
    ])
    print(f"  PostgreSQL {pg_version} installed.")


def cluster_exists(pg_version: int, cluster_name: str) -> bool:
    """Check if a PostgreSQL cluster exists.

    Args:
        pg_version: PostgreSQL major version.
        cluster_name: Cluster name.

    Returns:
        True if cluster exists.
    """
    result = _run(
        ["pg_lsclusters", "-h"],
        check=False,
        capture=True,
    )
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == str(pg_version) and parts[1] == cluster_name:
            return True
    return False


def create_cluster(pg_version: int, instance: InstanceConfig) -> None:
    """Create a PostgreSQL cluster using pg_createcluster.

    Initialises a new cluster with trust-based local auth so the start
    command can connect via socket without a password to bootstrap users.

    Args:
        pg_version: PostgreSQL major version.
        instance: Instance configuration containing cluster_name and port.
    """
    if cluster_exists(pg_version, instance.cluster_name):
        print(f"  Cluster {pg_version}/{instance.cluster_name} already exists, skipping.")
        return

    print(f"Creating cluster {pg_version}/{instance.cluster_name} on port {instance.port}...")
    _run([
        "pg_createcluster",
        str(pg_version),
        instance.cluster_name,
        f"--port={instance.port}",
        "--",
        "--auth-local=trust",
        "--auth-host=scram-sha-256",
    ])
    print(f"  Cluster {pg_version}/{instance.cluster_name} created.")


def start_cluster(pg_version: int, cluster_name: str) -> None:
    """Start a PostgreSQL cluster.

    Args:
        pg_version: PostgreSQL major version.
        cluster_name: Cluster name.
    """
    print(f"Starting cluster {pg_version}/{cluster_name}...")
    _run(["pg_ctlcluster", str(pg_version), cluster_name, "start"])
    # Allow a moment for the server to become ready
    time.sleep(2)
    print(f"  Cluster {pg_version}/{cluster_name} started.")


def stop_cluster(pg_version: int, cluster_name: str) -> None:
    """Stop a PostgreSQL cluster.

    Args:
        pg_version: PostgreSQL major version.
        cluster_name: Cluster name.
    """
    print(f"Stopping cluster {pg_version}/{cluster_name}...")
    _run(
        ["pg_ctlcluster", str(pg_version), cluster_name, "stop", "--", "-m", "fast"],
        check=False,
    )
    print(f"  Cluster {pg_version}/{cluster_name} stopped.")


def _socket_connect(
    port: int,
    user: str = "postgres",
) -> psycopg.Connection[tuple[object, ...]]:
    """Connect to PostgreSQL via unix socket (peer/trust auth).

    Args:
        port: Port number (used to locate the correct socket).
        user: Database user (default: postgres superuser).

    Returns:
        Open psycopg connection with autocommit enabled.
    """
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="/var/run/postgresql",
        port=port,
        user=user,
        dbname="postgres",
        autocommit=True,
    )
    return conn


def create_admin_user(instance: InstanceConfig, password: str) -> None:
    """Create the admin user in an instance with the supplied password.

    Connects via the unix socket as the postgres superuser (trust auth),
    then creates/updates the named role.

    Args:
        instance: Instance configuration.
        password: Password to set for the admin user.
    """
    print(f"  Creating admin user '{instance.admin_user}' on port {instance.port}...")
    role_ident = sql.Identifier(instance.admin_user)
    with _socket_connect(instance.port) as conn:
        try:
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN SUPERUSER PASSWORD %s"
                ).format(role_ident),
                (password,),
            )
        except errors.DuplicateObject:
            # Role already exists – update the password
            conn.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN SUPERUSER PASSWORD %s"
                ).format(role_ident),
                (password,),
            )
    print(f"  Admin user '{instance.admin_user}' ready.")


def _tcp_connect(
    instance: InstanceConfig,
    password: str,
    database: str = "postgres",
) -> psycopg.Connection[tuple[object, ...]]:
    """Connect to PostgreSQL via TCP using admin credentials.

    Args:
        instance: Instance configuration.
        password: Admin user password.
        database: Database to connect to.

    Returns:
        Open psycopg connection with autocommit enabled.
    """
    conn: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host="localhost",
        port=instance.port,
        user=instance.admin_user,
        password=password,
        dbname=database,
        autocommit=True,
    )
    return conn


def create_database(instance: InstanceConfig, password: str, db_name: str) -> None:
    """Create a database in an instance if it does not already exist.

    Args:
        instance: Instance configuration.
        password: Admin user password.
        db_name: Name of the database to create.
    """
    print(f"  Creating database '{db_name}' on port {instance.port}...")
    with _tcp_connect(instance, password) as conn:
        result = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,),
        ).fetchone()
        if result is None:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
            )
            print(f"  Database '{db_name}' created.")
        else:
            print(f"  Database '{db_name}' already exists.")


def create_table(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    table_name: str,
) -> None:
    """Create the demo table in the specified database.

    Args:
        instance: Instance configuration.
        password: Admin user password.
        db_name: Database name.
        table_name: Table name.
    """
    print(f"  Creating table '{table_name}' in '{db_name}' on port {instance.port}...")
    with _tcp_connect(instance, password, db_name) as conn:
        conn.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id        SERIAL PRIMARY KEY,
                    instance  TEXT        NOT NULL,
                    message   TEXT        NOT NULL,
                    created   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            ).format(tbl=sql.Identifier(table_name))
        )
    print(f"  Table '{table_name}' ready.")


def insert_row(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    table_name: str,
    message: str,
) -> int:
    """Insert a row into the demo table and return the new id.

    Args:
        instance: Instance configuration.
        password: Admin user password.
        db_name: Database name.
        table_name: Table name.
        message: Message to insert.

    Returns:
        The id of the newly inserted row.
    """
    print(f"  Inserting row into '{table_name}' on port {instance.port}...")
    with _tcp_connect(instance, password, db_name) as conn:
        row = conn.execute(
            sql.SQL(
                "INSERT INTO {tbl} (instance, message) VALUES (%s, %s) RETURNING id"
            ).format(tbl=sql.Identifier(table_name)),
            (instance.cluster_name, message),
        ).fetchone()
    if row is None:
        raise PostgresError("INSERT did not return a row id")
    inserted_id = int(row[0])  # type: ignore[arg-type]
    print(f"  Inserted row with id={inserted_id}.")
    return inserted_id


def query_rows(
    instance: InstanceConfig,
    password: str,
    db_name: str,
    table_name: str,
) -> list[dict[str, object]]:
    """Query all rows from the demo table.

    Args:
        instance: Instance configuration.
        password: Admin user password.
        db_name: Database name.
        table_name: Table name.

    Returns:
        List of row dicts with keys id, instance, message, created.
    """
    with _tcp_connect(instance, password, db_name) as conn:
        cursor = conn.execute(
            sql.SQL(
                "SELECT id, instance, message, created FROM {tbl} ORDER BY id"
            ).format(tbl=sql.Identifier(table_name))
        )
        columns = [desc[0] for desc in cursor.description or []]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return rows


# ---------------------------------------------------------------------------
# High-level orchestration helpers (used by CLI)
# ---------------------------------------------------------------------------

def install_all(config: AppConfig) -> None:
    """Full installation: add PGDG repo, install PG, create both clusters.

    Args:
        config: Application configuration.
    """
    add_pgdg_repo()
    install_postgres(config.pg_version)
    create_cluster(config.pg_version, config.instance1)
    create_cluster(config.pg_version, config.instance2)


def start_all(config: AppConfig, password1: str, password2: str) -> None:
    """Start both clusters and ensure admin users exist.

    Args:
        config: Application configuration.
        password1: Password for instance 1 admin user.
        password2: Password for instance 2 admin user.
    """
    start_cluster(config.pg_version, config.instance1.cluster_name)
    start_cluster(config.pg_version, config.instance2.cluster_name)
    create_admin_user(config.instance1, password1)
    create_admin_user(config.instance2, password2)


def create_table_all(config: AppConfig, password1: str, password2: str) -> None:
    """Create databases and tables in both instances.

    Args:
        config: Application configuration.
        password1: Password for instance 1 admin user.
        password2: Password for instance 2 admin user.
    """
    db = config.database.name
    tbl = config.database.table_name

    create_database(config.instance1, password1, db)
    create_database(config.instance2, password2, db)
    create_table(config.instance1, password1, db, tbl)
    create_table(config.instance2, password2, db, tbl)


def insert_all(config: AppConfig, password1: str, password2: str) -> None:
    """Insert a distinct row into each instance.

    Args:
        config: Application configuration.
        password1: Password for instance 1 admin user.
        password2: Password for instance 2 admin user.
    """
    db = config.database.name
    tbl = config.database.table_name

    insert_row(
        config.instance1,
        password1,
        db,
        tbl,
        f"Hello from instance 1 ({config.instance1.cluster_name})",
    )
    insert_row(
        config.instance2,
        password2,
        db,
        tbl,
        f"Hello from instance 2 ({config.instance2.cluster_name})",
    )


def query_all(
    config: AppConfig,
    password1: str,
    password2: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Query rows from both instances and return them.

    Args:
        config: Application configuration.
        password1: Password for instance 1 admin user.
        password2: Password for instance 2 admin user.

    Returns:
        Tuple of (rows_from_instance1, rows_from_instance2).
    """
    db = config.database.name
    tbl = config.database.table_name

    rows1 = query_rows(config.instance1, password1, db, tbl)
    rows2 = query_rows(config.instance2, password2, db, tbl)
    return rows1, rows2
