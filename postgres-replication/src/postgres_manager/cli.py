"""Click CLI for managing PostgreSQL instances."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from .config import (
    DEFAULT_CONFIG_PATH,
    ReplicationConfig,
    load_config,
    resolve_instance,
    save_replication_config,
)
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

_dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help=(
        "Print all SQL / DDL that would be executed without making any changes "
        "to any database or cluster."
    ),
)


def _require_password(password: str | None, instance_name: str) -> str:
    """Return the password or exit with a helpful error."""
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

    Pass --dry-run to any command to see the SQL/commands it would execute
    without actually making any changes.
    """


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@main.command()
@_config_option
@_instance_option
@_dry_run_option
def install(config: Path | None, instance: str | None, dry_run: bool) -> None:
    """Install PostgreSQL and initialise a cluster.

    Adds the PGDG apt repository, installs the postgresql-<version> package
    (if not already present), and calls pg_createcluster for the selected
    instance.  Requires root / sudo.
    """
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        if dry_run:
            click.echo(f"[DRY RUN] Would install PostgreSQL {cfg.pg_version} for '{inst.cluster_name}'")
        else:
            click.echo(f"Installing PostgreSQL {cfg.pg_version} for '{inst.cluster_name}'...")
        add_pgdg_repo()
        install_postgres(cfg.pg_version, dry_run=dry_run)
        create_cluster(cfg.pg_version, inst, dry_run=dry_run)
        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
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
@_dry_run_option
def start(
    config: Path | None,
    instance: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Start a cluster and ensure the admin user exists.

    Requires root / sudo.  Admin users are created (or their passwords
    updated) on first start.
    """
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        pw = _require_password(password, inst.cluster_name)
        if dry_run:
            click.echo(f"[DRY RUN] Would start cluster '{inst.cluster_name}'")
        else:
            click.echo(f"Starting cluster '{inst.cluster_name}'...")
        start_cluster(cfg.pg_version, inst.cluster_name, dry_run=dry_run)
        create_admin_user(inst, pw, dry_run=dry_run)
        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
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
@_dry_run_option
def stop(config: Path | None, instance: str | None, dry_run: bool) -> None:
    """Stop a cluster."""
    try:
        cfg = load_config(config)
        inst = resolve_instance(cfg, instance)
        stop_cluster(cfg.pg_version, inst.cluster_name, dry_run=dry_run)
        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
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
@_dry_run_option
def create_table_cmd(
    config: Path | None,
    instance: str | None,
    password: str | None,
    dry_run: bool,
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
        if dry_run:
            click.echo(
                f"[DRY RUN] Would create database '{db}' and table '{tbl}'"
                f" in '{inst.cluster_name}'"
            )
        else:
            click.echo(
                f"Creating database '{db}' and table '{tbl}' in '{inst.cluster_name}'..."
            )
        create_database(inst, pw, db, dry_run=dry_run)
        create_table(inst, pw, db, tbl, dry_run=dry_run)
        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
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
@_dry_run_option
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
    dry_run: bool,
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
        row_id = insert_row(inst, pw, db, tbl, msg, dry_run=dry_run)
        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
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


# ---------------------------------------------------------------------------
# replication command group
# ---------------------------------------------------------------------------


@main.group()
def replication() -> None:
    """Logical replication setup and monitoring."""


# ---- prepare ---------------------------------------------------------------


@replication.command("prepare")
@_config_option
@click.option("--publisher", "publisher_name", required=True, metavar="NAME",
              help="Cluster name of the publisher instance.")
@click.option("--subscriber", "subscriber_name", required=True, metavar="NAME",
              help="Cluster name of the subscriber instance.")
@click.option("--pub-password", envvar="PGPASSWORD_PUB", required=True,
              help="Admin password for the publisher (or PGPASSWORD_PUB).")
@click.option("--sub-password", envvar="PGPASSWORD_SUB", required=True,
              help="Admin password for the subscriber (or PGPASSWORD_SUB).")
@click.option("--replication-user", default="replicator",
              show_default=True, help="Name of the replication role to create.")
@click.option("--publication-name", default=None, metavar="NAME",
              help="Publication name. Defaults to '<publisher>_pub'.")
@click.option("--subscription-name", default=None, metavar="NAME",
              help="Subscription name. Defaults to '<subscriber>_sub'.")
@_dry_run_option
def replication_prepare(
    config: Path | None,
    publisher_name: str,
    subscriber_name: str,
    pub_password: str,
    sub_password: str,
    replication_user: str,
    publication_name: str | None,
    subscription_name: str | None,
    dry_run: bool,
) -> None:
    """Compare publisher and subscriber tables and write replication config.

    Queries all user tables from the publisher, checks which exist on the
    subscriber, and assigns each a status: create / alter / exists /
    incompatible.  The result is written to config.toml under [replication].

    Publication and subscription names are auto-generated from cluster names
    if not specified (e.g. ``main1_pub`` / ``main2_sub``).
    """
    from .replication import ReplicationError, compare_tables, get_table_columns

    try:
        cfg = load_config(config)
        config_path = config or DEFAULT_CONFIG_PATH

        pub = resolve_instance(cfg, publisher_name)
        sub = resolve_instance(cfg, subscriber_name)
        db = cfg.database.name

        # Apply sensible defaults for optional names
        eff_pub_name = publication_name or f"{pub.cluster_name}_pub"
        eff_sub_name = subscription_name or f"{sub.cluster_name}_sub"

        click.echo(f"Querying tables from publisher '{pub.cluster_name}'...")
        pub_cols = get_table_columns(pub, pub_password, db)
        click.echo(f"Querying tables from subscriber '{sub.cluster_name}'...")
        sub_cols = get_table_columns(sub, sub_password, db)

        entries = compare_tables(pub_cols, sub_cols)

        rep = ReplicationConfig(
            publisher_instance=publisher_name,
            subscriber_instance=subscriber_name,
            publication_name=eff_pub_name,
            subscription_name=eff_sub_name,
            replication_user=replication_user,
            tables=entries,
        )

        click.echo(f"\nFound {len(entries)} table(s):")
        for e in entries:
            click.echo(f"  [{e.status:>12}]  {e.schema}.{e.name}")
        click.echo(f"\n  publication_name  = {eff_pub_name}")
        click.echo(f"  subscription_name = {eff_sub_name}")
        click.echo(f"  replication_user  = {replication_user}")

        if dry_run:
            click.echo(f"\n[DRY RUN] Would write replication config to {config_path}.")
            click.echo("[DRY RUN] No changes made.")
        else:
            save_replication_config(config_path, rep)
            click.echo(f"\nReplication config written to {config_path}.")

    except (FileNotFoundError, KeyError, ValueError, ReplicationError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---- setup-publisher -------------------------------------------------------


@replication.command("setup-publisher")
@_config_option
@_password_option
@_dry_run_option
@click.option("--replication-password", envvar="PGREPLICATION_PASSWORD", required=True,
              help="Password for the replication role (or PGREPLICATION_PASSWORD).")
def replication_setup_publisher(
    config: Path | None,
    password: str | None,
    dry_run: bool,
    replication_password: str,
) -> None:
    """Configure the publisher: wal_level, replication user, and publication.

    Reads [replication] from config.toml for publication name, replication
    user, and the table list.  Sets wal_level = logical (restarting if needed),
    creates the replication role, grants SELECT on the tables, and creates
    the publication.
    """
    from .replication import (
        ReplicationError,
        create_replication_user,
        ensure_wal_logical,
        setup_publication,
    )

    try:
        cfg = load_config(config)
        rep = cfg.replication
        if rep is None:
            click.echo(
                "Error: no [replication] section in config. Run 'replication prepare' first.",
                err=True,
            )
            sys.exit(1)

        pub = resolve_instance(cfg, rep.publisher_instance)
        pw = _require_password(password, pub.cluster_name)
        db = cfg.database.name

        tables = [(t.schema, t.name) for t in rep.tables
                  if t.status in ("create", "exists", "alter")]
        if not tables:
            click.echo("No tables eligible for replication (all incompatible or none listed).")
            sys.exit(1)

        click.echo(f"{'[DRY RUN] ' if dry_run else ''}Setting up publisher '{pub.cluster_name}'...")
        ensure_wal_logical(cfg.pg_version, pub.cluster_name, pub, pw, dry_run=dry_run)
        create_replication_user(pub, pw, rep.replication_user, replication_password, db, tables,
                                dry_run=dry_run)
        setup_publication(pub, pw, db, rep.publication_name, tables, dry_run=dry_run)

        if dry_run:
            click.echo("[DRY RUN] No changes made.")
        else:
            click.echo("Publisher setup complete.")

    except (FileNotFoundError, KeyError, ValueError, ReplicationError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---- setup-subscriber ------------------------------------------------------


@replication.command("setup-subscriber")
@_config_option
@_password_option
@_dry_run_option
@click.option("--replication-password", envvar="PGREPLICATION_PASSWORD", required=True,
              help="Password for the replication role (or PGREPLICATION_PASSWORD).")
@click.option("--publisher-host", default="localhost", show_default=True,
              help="Hostname the subscriber uses to reach the publisher.")
@click.option("--pub-password", envvar="PGPASSWORD_PUB", default=None,
              help="Publisher admin password for fetching DDL (or PGPASSWORD_PUB). "
                   "Defaults to --password if not set.")
def replication_setup_subscriber(
    config: Path | None,
    password: str | None,
    dry_run: bool,
    replication_password: str,
    publisher_host: str,
    pub_password: str | None,
) -> None:
    """Configure the subscriber: create missing tables and subscription.

    Reads [replication] from config.toml for subscription name, publication
    name, and the table list.  Creates any tables on the subscriber that are
    marked 'create', then creates the subscription pointing at the publisher.

    After creating the subscription, polls the publisher every 2 seconds for
    up to 30 seconds, reporting bytes remaining and estimated catch-up time.
    """
    from .replication import (
        ReplicationError,
        create_table_on_subscriber,
        poll_until_caught_up,
        setup_subscription,
    )

    try:
        cfg = load_config(config)
        rep = cfg.replication
        if rep is None:
            click.echo(
                "Error: no [replication] section in config. Run 'replication prepare' first.",
                err=True,
            )
            sys.exit(1)

        pub = resolve_instance(cfg, rep.publisher_instance)
        sub = resolve_instance(cfg, rep.subscriber_instance)
        sub_pw = _require_password(password, sub.cluster_name)
        eff_pub_pw = pub_password or sub_pw
        db = cfg.database.name

        tables_to_create = [(t.schema, t.name) for t in rep.tables if t.status == "create"]
        if tables_to_create:
            click.echo(
                f"{'[DRY RUN] ' if dry_run else ''}"
                f"Creating {len(tables_to_create)} table(s) on subscriber..."
            )
            for schema, table in tables_to_create:
                create_table_on_subscriber(
                    pub, eff_pub_pw, sub, sub_pw, db, schema, table, dry_run=dry_run
                )

        click.echo(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Setting up subscription '{rep.subscription_name}'..."
        )
        setup_subscription(
            subscriber=sub,
            sub_password=sub_pw,
            db_name=db,
            subscription_name=rep.subscription_name,
            publisher_host=publisher_host,
            publisher_port=pub.port,
            replication_user=rep.replication_user,
            replication_password=replication_password,
            publication_name=rep.publication_name,
            dry_run=dry_run,
        )

        if dry_run:
            click.echo("[DRY RUN] No changes made.")
            return

        click.echo("Subscriber setup complete.")

        # Poll replication catch-up on the publisher
        click.echo("\nPolling replication catch-up on publisher...")
        poll_until_caught_up(pub, eff_pub_pw)

    except (FileNotFoundError, KeyError, ValueError, ReplicationError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---- monitor ---------------------------------------------------------------


@replication.command("monitor")
@_config_option
@_password_option
@click.option("--sub-password", envvar="PGPASSWORD_SUB", default=None,
              help="Subscriber admin password for --counts (or PGPASSWORD_SUB). "
                   "Defaults to --password if not set.")
@click.option("--counts", "show_counts", is_flag=True, default=False,
              help=(
                  "Compare row counts for each replicated table across publisher "
                  "and subscriber.  Highlights mismatches and shows max primary-key "
                  "values for any tables where counts differ."
              ))
def replication_monitor(
    config: Path | None,
    password: str | None,
    sub_password: str | None,
    show_counts: bool,
) -> None:
    """Show replication status from the publisher.

    Queries pg_stat_replication (connected subscribers) and
    pg_replication_slots (logical slot lag in bytes).

    If outstanding lag is detected, automatically polls every 2 seconds for
    up to 30 seconds reporting progress until replication catches up.

    Pass --counts to compare row counts across publisher and subscriber.
    """
    from .replication import (
        ReplicationError,
        get_max_pk_values,
        get_pk_columns,
        get_replication_stats,
        get_row_counts,
        poll_until_caught_up,
    )

    try:
        cfg = load_config(config)
        rep = cfg.replication
        if rep is None:
            click.echo(
                "Error: no [replication] section in config. Run 'replication prepare' first.",
                err=True,
            )
            sys.exit(1)

        pub = resolve_instance(cfg, rep.publisher_instance)
        pw = _require_password(password, pub.cluster_name)

        connections, slots = get_replication_stats(pub, pw)

        click.echo(click.style(
            f"=== Publisher: {pub.cluster_name} (port {pub.port}) ===", bold=True
        ))

        click.echo(click.style("\nConnected subscribers (pg_stat_replication):", bold=True))
        if not connections:
            click.echo("  (none)")
        else:
            for c in connections:
                click.echo(
                    f"  {c['application_name']}  state={c['state']}  "
                    f"sent={c['sent_lsn']}  replay={c['replay_lsn']}  "
                    f"lag={c['replay_lag']}"
                )

        click.echo(click.style("\nLogical replication slots (pg_replication_slots):", bold=True))
        if not slots:
            click.echo("  (none)")
        else:
            for s in slots:
                active = "active" if s["active"] else "inactive"
                click.echo(
                    f"  {s['slot_name']}  [{active}]  "
                    f"lag={s['lag_pretty']}  ({s['lag_bytes']} bytes)"
                )

        # If there is outstanding lag, poll until caught up
        total_lag = sum(int(str(s["lag_bytes"])) for s in slots)
        if total_lag > 0:
            click.echo("")
            poll_until_caught_up(pub, pw)

        # --counts: row-count comparison across publisher and subscriber
        if show_counts:
            eff_sub_pw = sub_password or pw
            sub = resolve_instance(cfg, rep.subscriber_instance)
            db = cfg.database.name
            tables = [(t.schema, t.name) for t in rep.tables]

            click.echo(click.style("\nRow count comparison:", bold=True))
            if not tables:
                click.echo("  (no tables in replication config)")
            else:
                pub_counts = get_row_counts(pub, pw, db, tables)
                sub_counts = get_row_counts(sub, eff_sub_pw, db, tables)

                col_w = max(len(f"{s}.{t}") for s, t in tables) + 2
                hdr = (
                    f"  {'Table':<{col_w}}  {'Publisher':>12}  {'Subscriber':>12}  Match"
                )
                click.echo(hdr)
                click.echo(f"  {'-'*col_w}  {'-'*12}  {'-'*12}  -----")

                for schema, table in tables:
                    pc = pub_counts.get((schema, table), -1)
                    sc = sub_counts.get((schema, table), -1)
                    match = pc == sc
                    pc_str = str(pc) if pc >= 0 else "N/A"
                    sc_str = str(sc) if sc >= 0 else "N/A"
                    marker = "  OK" if match else "  MISMATCH <<<"
                    click.echo(
                        f"  {schema}.{table:<{col_w - len(schema) - 1}}"
                        f"  {pc_str:>12}  {sc_str:>12}{marker}"
                    )

                    if not match and pc >= 0 and sc >= 0:
                        # Show max PK values to help diagnose
                        pk_cols = get_pk_columns(pub, pw, db, schema, table)
                        if pk_cols:
                            pub_max = get_max_pk_values(pub, pw, db, schema, table, pk_cols)
                            sub_max = get_max_pk_values(sub, eff_sub_pw, db, schema, table, pk_cols)
                            for col in pk_cols:
                                click.echo(
                                    f"    max({col}): publisher={pub_max.get(col)}  "
                                    f"subscriber={sub_max.get(col)}"
                                )

    except (FileNotFoundError, KeyError, ValueError, ReplicationError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
