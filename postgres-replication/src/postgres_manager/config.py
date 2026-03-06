"""Configuration loading and management for postgres-manager."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.toml"


@dataclass
class InstanceConfig:
    """Configuration for a single PostgreSQL instance."""

    cluster_name: str
    port: int
    admin_user: str
    data_dir: str
    socket_dir: str


@dataclass
class DatabaseConfig:
    """Configuration for the database and table."""

    name: str
    table_name: str


@dataclass
class AppConfig:
    """Full application configuration."""

    pg_version: int
    instance1: InstanceConfig
    instance2: InstanceConfig
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
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    pg_version: int = data["postgres"]["version"]

    def parse_instance(section: dict[str, object]) -> InstanceConfig:
        return InstanceConfig(
            cluster_name=str(section["cluster_name"]),
            port=int(section["port"]),  # type: ignore[arg-type]
            admin_user=str(section["admin_user"]),
            data_dir=str(section["data_dir"]),
            socket_dir=str(section["socket_dir"]),
        )

    instance1 = parse_instance(data["instance1"])
    instance2 = parse_instance(data["instance2"])

    db_section: dict[str, object] = data["database"]
    table_section: dict[str, object] = data["table"]
    database = DatabaseConfig(
        name=str(db_section["name"]),
        table_name=str(table_section["name"]),
    )

    return AppConfig(
        pg_version=pg_version,
        instance1=instance1,
        instance2=instance2,
        database=database,
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
