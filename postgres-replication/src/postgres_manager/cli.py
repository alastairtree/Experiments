"""Click CLI for managing two PostgreSQL 18 instances."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from .config import DEFAULT_CONFIG_PATH, load_config
from .postgres import (
    PostgresError,
    create_table_all,
    insert_all,
    install_all,
    query_all,
    start_all,
    stop_cluster,
)


def _get_passwords(
    password1: str | None,
    password2: str | None,
) -> tuple[str, str]:
    """Resolve passwords from CLI args or environment variables.

    Priority: CLI arg > env var.  Exits with an error if either is missing.

    Args:
        password1: Password for instance 1, or None to read env.
        password2: Password for instance 2, or None to read env.

    Returns:
        Tuple of (password1, password2).
    """
    p1 = password1 or os.environ.get("PGPASSWORD1", "")
    p2 = password2 or os.environ.get("PGPASSWORD2", "")

    missing: list[str] = []
    if not p1:
        missing.append("--password1 / PGPASSWORD1")
    if not p2:
        missing.append("--password2 / PGPASSWORD2")

    if missing:
        click.echo(
            f"Error: missing required passwords: {', '.join(missing)}\n"
            "Provide them via --password1/--password2 or the PGPASSWORD1/PGPASSWORD2 "
            "environment variables.",
            err=True,
        )
        sys.exit(1)

    return p1, p2


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_config_option = click.option(
    "--config",
    "-c",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help=f"Path to config.toml file. Defaults to {DEFAULT_CONFIG_PATH}.",
)

_password_options = [
    click.option(
        "--password1",
        envvar="PGPASSWORD1",
        default=None,
        help="Admin password for instance 1 (or set PGPASSWORD1).",
    ),
    click.option(
        "--password2",
        envvar="PGPASSWORD2",
        default=None,
        help="Admin password for instance 2 (or set PGPASSWORD2).",
    ),
]


def _add_password_options(func: click.decorators.FC) -> click.decorators.FC:
    """Decorator that adds both password options to a command."""
    for option in reversed(_password_options):
        func = option(func)
    return func


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option()
def main() -> None:
    """Manage two PostgreSQL 18 instances on the local machine.

    Use PGPASSWORD1 / PGPASSWORD2 environment variables (or --password1 /
    --password2 flags) to supply admin passwords without storing them in the
    config file.
    """


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@main.command()
@_config_option
def install(config: Path | None) -> None:
    """Install PostgreSQL 18 and initialise both clusters.

    This command requires root / sudo privileges.
    It adds the PGDG apt repository, installs the postgresql-18 package,
    and calls pg_createcluster for each instance defined in config.toml.
    """
    try:
        cfg = load_config(config)
        click.echo(f"Installing PostgreSQL {cfg.pg_version} and creating clusters...")
        install_all(cfg)
        click.echo("Installation complete.")
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_add_password_options
def start(
    config: Path | None,
    password1: str | None,
    password2: str | None,
) -> None:
    """Start both PostgreSQL clusters and create admin users.

    This command requires root / sudo privileges.
    Admin users are created (or their passwords updated) on first start.
    """
    p1, p2 = _get_passwords(password1, password2)
    try:
        cfg = load_config(config)
        click.echo("Starting clusters and configuring admin users...")
        start_all(cfg, p1, p2)
        click.echo("Both clusters started.")
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@main.command()
@_config_option
def stop(config: Path | None) -> None:
    """Stop both PostgreSQL clusters."""
    try:
        cfg = load_config(config)
        stop_cluster(cfg.pg_version, cfg.instance1.cluster_name)
        stop_cluster(cfg.pg_version, cfg.instance2.cluster_name)
        click.echo("Both clusters stopped.")
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# create-table
# ---------------------------------------------------------------------------


@main.command("create-table")
@_config_option
@_add_password_options
def create_table(
    config: Path | None,
    password1: str | None,
    password2: str | None,
) -> None:
    """Create the database and demo table in both instances.

    Creates the database specified in config.toml (same name in each instance)
    and then creates a table named 'demo' (or whatever is configured) in each.
    """
    p1, p2 = _get_passwords(password1, password2)
    try:
        cfg = load_config(config)
        db = cfg.database.name
        tbl = cfg.database.table_name
        click.echo(f"Creating database '{db}' and table '{tbl}' in both instances...")
        create_table_all(cfg, p1, p2)
        click.echo("Database and table created in both instances.")
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_add_password_options
def insert(
    config: Path | None,
    password1: str | None,
    password2: str | None,
) -> None:
    """Insert a unique row into the demo table in each instance.

    Each instance receives a different message row, demonstrating that the
    two instances are independent.
    """
    p1, p2 = _get_passwords(password1, password2)
    try:
        cfg = load_config(config)
        click.echo("Inserting rows into both instances...")
        insert_all(cfg, p1, p2)
        click.echo("Rows inserted into both instances.")
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_add_password_options
def query(
    config: Path | None,
    password1: str | None,
    password2: str | None,
) -> None:
    """Query the demo table from both instances and display results.

    Demonstrates that each instance holds its own independent data.
    """
    p1, p2 = _get_passwords(password1, password2)
    try:
        cfg = load_config(config)
        db = cfg.database.name
        tbl = cfg.database.table_name
        click.echo(f"Querying '{tbl}' in '{db}' from both instances...\n")
        rows1, rows2 = query_all(cfg, p1, p2)

        _print_results(
            f"Instance 1 ({cfg.instance1.cluster_name}, port {cfg.instance1.port})",
            rows1,
        )
        _print_results(
            f"Instance 2 ({cfg.instance2.cluster_name}, port {cfg.instance2.port})",
            rows2,
        )

        if rows1 and rows2:
            if rows1 != rows2:
                click.echo(
                    click.style(
                        "✓ Instances hold different data — confirmed independent instances.",
                        fg="green",
                    )
                )
            else:
                click.echo(
                    click.style(
                        "⚠  Instances hold identical data.",
                        fg="yellow",
                    )
                )
    except (FileNotFoundError, KeyError, PostgresError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _print_results(label: str, rows: list[dict[str, object]]) -> None:
    """Pretty-print query results.

    Args:
        label: Section heading.
        rows: List of row dicts.
    """
    click.echo(click.style(f"--- {label} ---", bold=True))
    if not rows:
        click.echo("  (no rows)")
    else:
        for row in rows:
            click.echo(
                f"  id={row['id']}  instance={row['instance']!r}  "
                f"message={row['message']!r}  created={row['created']}"
            )
    click.echo()
