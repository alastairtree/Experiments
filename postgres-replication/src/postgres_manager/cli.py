"""Click CLI for managing PostgreSQL instances."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from .config import DEFAULT_CONFIG_PATH, AppConfig, load_config, resolve_instance
from .postgres import (
    PostgresError,
    create_admin_user,
    create_database,
    create_table,
    create_cluster,
    install_postgres,
    add_pgdg_repo,
    insert_row,
    query_rows,
    start_cluster,
    stop_cluster,
)


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_config_option = click.option(
    "--config",
    "-c",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help=f"Path to config.toml. Defaults to {DEFAULT_CONFIG_PATH}.",
)

_instance_option = click.option(
    "--instance",
    "-i",
    default=None,
    metavar="NAME",
    help=(
        "Cluster name or 1-based index of the instance to operate on. "
        "Required when the config defines more than one instance."
    ),
)

_password_option = click.option(
    "--password",
    envvar="PGPASSWORD",
    default=None,
    help="Admin password for the selected instance (or set PGPASSWORD).",
)


def _require_password(password: str | None, instance_name: str) -> str:
    """Return the password or exit with a helpful error.

    Args:
        password: Value from CLI / env, may be None.
        instance_name: Human-readable instance identifier for the error message.

    Returns:
        Non-empty password string.
    """
    pw = password or os.environ.get("PGPASSWORD", "")
    if not pw:
        click.echo(
            f"Error: no password supplied for instance '{instance_name}'.\n"
            "Use --password or set the PGPASSWORD environment variable.",
            err=True,
        )
        sys.exit(1)
    return pw


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option()
def main() -> None:
    """Manage one or more PostgreSQL instances on the local machine.

    Each command targets a single instance selected with --instance NAME (or the
    cluster's 1-based position in config.toml).  When only one instance is
    configured the --instance flag is optional.

    Passwords are never stored in the config file.  Supply them via
    --password or the PGPASSWORD environment variable.
    """


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
def install(config: Path | None, instance: str | None) -> None:
    """Install PostgreSQL and initialise a cluster.

    Adds the PGDG apt repository, installs the postgresql-<version> package
    (if not already present), and calls pg_createcluster for the selected
    instance.  Requires root / sudo.
    """
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        click.echo(f"Installing PostgreSQL {cfg.pg_version} for '{inst.cluster_name}'...")
        add_pgdg_repo()
        install_postgres(cfg.pg_version)
        create_cluster(cfg.pg_version, inst)
        click.echo("Installation complete.")
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
@_password_option
def start(
    config: Path | None,
    instance: str | None,
    password: str | None,
) -> None:
    """Start a cluster and ensure the admin user exists.

    Requires root / sudo.  Admin users are created (or their passwords
    updated) on first start.
    """
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        pw = _require_password(password, inst.cluster_name)
        click.echo(f"Starting cluster '{inst.cluster_name}'...")
        start_cluster(cfg.pg_version, inst.cluster_name)
        create_admin_user(inst, pw)
        click.echo(f"Cluster '{inst.cluster_name}' started.")
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
def stop(config: Path | None, instance: str | None) -> None:
    """Stop a cluster."""
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        stop_cluster(cfg.pg_version, inst.cluster_name)
        click.echo(f"Cluster '{inst.cluster_name}' stopped.")
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# create-table
# ---------------------------------------------------------------------------


@main.command("create-table")
@_config_option
@_instance_option
@_password_option
def create_table_cmd(
    config: Path | None,
    instance: str | None,
    password: str | None,
) -> None:
    """Create the database and demo table in an instance.

    Creates the database specified in config.toml (if it does not already
    exist) and then creates the demo table inside it.
    """
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        pw = _require_password(password, inst.cluster_name)
        db = cfg.database.name
        tbl = cfg.database.table_name
        click.echo(
            f"Creating database '{db}' and table '{tbl}' in '{inst.cluster_name}'..."
        )
        create_database(inst, pw, db)
        create_table(inst, pw, db, tbl)
        click.echo("Done.")
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
@_password_option
@click.option(
    "--message",
    "-m",
    default=None,
    help="Custom message to insert. Defaults to a generated message.",
)
def insert(
    config: Path | None,
    instance: str | None,
    password: str | None,
    message: str | None,
) -> None:
    """Insert a row into the demo table."""
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        pw = _require_password(password, inst.cluster_name)
        db = cfg.database.name
        tbl = cfg.database.table_name
        msg = message or f"Hello from instance '{inst.cluster_name}'"
        row_id = insert_row(inst, pw, db, tbl, msg)
        click.echo(f"Inserted row id={row_id} into '{inst.cluster_name}'.")
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
@_password_option
def query(
    config: Path | None,
    instance: str | None,
    password: str | None,
) -> None:
    """Query the demo table from an instance and display results."""
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        pw = _require_password(password, inst.cluster_name)
        db = cfg.database.name
        tbl = cfg.database.table_name
        rows = query_rows(inst, pw, db, tbl)
        click.echo(
            click.style(
                f"--- {inst.cluster_name} (port {inst.port}) ---",
                bold=True,
            )
        )
        if not rows:
            click.echo("  (no rows)")
        else:
            for row in rows:
                click.echo(
                    f"  id={row['id']}  instance={row['instance']!r}  "
                    f"message={row['message']!r}  created={row['created']}"
                )
    except (FileNotFoundError, KeyError, ValueError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
