"""Configuration loading and management for postgres-manager."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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
class AppConfig:
    """Full application configuration."""

    pg_version: int
    instances: list[InstanceConfig]
    database: DatabaseConfig


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

    return AppConfig(
        pg_version=pg_version,
        instances=instances,
        database=database,
    )


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

    # Match by cluster_name first
    for inst in config.instances:
        if inst.cluster_name == name_or_index:
            return inst

    # Fall back to 1-based index
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
