"""Configuration loading and management for postgres-manager."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.toml"


@dataclass
class InstanceConfig:
    """Configuration for a single PostgreSQL instance."""

    cluster_name: str
    port: int
    admin_user: str
    socket_dir: str = "/var/run/postgresql"


@dataclass
class DatabaseConfig:
    """Configuration for the database and table."""

    name: str
    table_name: str


@dataclass
class TableReplicationEntry:
    """Replication status for a single table."""

    schema: str
    name: str
    # "create"  – exists in publisher, missing in subscriber
    # "alter"   – exists in both but columns differ (subscriber is subset)
    # "exists"  – identical in both instances
    # "incompatible" – columns conflict; manual intervention required
    status: str


@dataclass
class ReplicationConfig:
    """Logical replication configuration."""

    publisher_instance: str
    subscriber_instance: str
    publication_name: str
    subscription_name: str
    replication_user: str
    tables: list[TableReplicationEntry] = field(default_factory=list)


@dataclass
class AppConfig:
    """Full application configuration."""

    pg_version: int
    instances: list[InstanceConfig]
    database: DatabaseConfig
    replication: ReplicationConfig | None = None


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from a TOML file.

    Args:
        config_path: Path to the config file. Defaults to config.toml in project root.

    Returns:
        Parsed AppConfig object.

    Raises:
        FileNotFoundError: If config file does not exist.
        KeyError: If required config keys are missing.
        ValueError: If no instances are defined.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    pg_version: int = data["postgres"]["version"]

    raw_instances: list[dict[str, object]] = data["instances"]
    if not raw_instances:
        raise ValueError("Config must define at least one [[instances]] entry")

    instances = [
        InstanceConfig(
            cluster_name=str(s["cluster_name"]),
            port=int(s["port"]),
            admin_user=str(s["admin_user"]),
            socket_dir=str(s.get("socket_dir", "/var/run/postgresql")),
        )
        for s in raw_instances
    ]

    db_section: dict[str, object] = data["database"]
    table_section: dict[str, object] = data["table"]
    database = DatabaseConfig(
        name=str(db_section["name"]),
        table_name=str(table_section["name"]),
    )

    replication: ReplicationConfig | None = None
    if "replication" in data:
        r: dict[str, object] = data["replication"]
        raw_tables: list[dict[str, object]] = r.get("tables", [])
        replication = ReplicationConfig(
            publisher_instance=str(r["publisher_instance"]),
            subscriber_instance=str(r["subscriber_instance"]),
            publication_name=str(r["publication_name"]),
            subscription_name=str(r["subscription_name"]),
            replication_user=str(r["replication_user"]),
            tables=[
                TableReplicationEntry(
                    schema=str(t["schema"]),
                    name=str(t["name"]),
                    status=str(t["status"]),
                )
                for t in raw_tables
            ],
        )

    return AppConfig(
        pg_version=pg_version,
        instances=instances,
        database=database,
        replication=replication,
    )


def save_replication_config(
    config_path: Path,
    replication: ReplicationConfig,
) -> None:
    """Write the replication section back to the TOML config file.

    Reads the existing file, replaces/adds the ``[replication]`` section, then
    writes the result back atomically.

    Args:
        config_path: Path to config.toml (must already exist).
        replication: The replication configuration to persist.
    """
    with open(config_path, "rb") as f:
        data: dict[str, object] = tomllib.load(f)

    data["replication"] = {
        "publisher_instance": replication.publisher_instance,
        "subscriber_instance": replication.subscriber_instance,
        "publication_name": replication.publication_name,
        "subscription_name": replication.subscription_name,
        "replication_user": replication.replication_user,
        "tables": [
            {"schema": t.schema, "name": t.name, "status": t.status}
            for t in replication.tables
        ],
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)


def resolve_instance(config: AppConfig, name_or_index: str | None) -> InstanceConfig:
    """Return the matching InstanceConfig.

    Rules:
    - If ``name_or_index`` is None and there is exactly one instance, return it.
    - If ``name_or_index`` matches a cluster_name, return that instance.
    - If ``name_or_index`` is a 1-based integer string, return by position.

    Args:
        config: Loaded application configuration.
        name_or_index: Cluster name, 1-based index string, or None.

    Returns:
        The matching InstanceConfig.

    Raises:
        ValueError: When the instance cannot be resolved.
    """
    if name_or_index is None:
        if len(config.instances) == 1:
            return config.instances[0]
        names = ", ".join(i.cluster_name for i in config.instances)
        raise ValueError(
            f"Multiple instances configured ({names}). "
            "Specify one with --instance NAME."
        )

    for inst in config.instances:
        if inst.cluster_name == name_or_index:
            return inst

    try:
        idx = int(name_or_index) - 1
        return config.instances[idx]
    except (ValueError, IndexError):
        pass

    names = ", ".join(i.cluster_name for i in config.instances)
    raise ValueError(
        f"Instance '{name_or_index}' not found. Available: {names}"
    )


def get_connection_string(
    instance: InstanceConfig,
    password: str,
    database: str = "postgres",
) -> str:
    """Build a psycopg connection string for an instance.

    Args:
        instance: Instance configuration.
        password: Password for the admin user.
        database: Database name to connect to.

    Returns:
        Connection string for psycopg.
    """
    return (
        f"host=localhost "
        f"port={instance.port} "
        f"user={instance.admin_user} "
        f"password={password} "
        f"dbname={database}"
    )
