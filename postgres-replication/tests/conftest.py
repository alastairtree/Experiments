"""Shared pytest fixtures for postgres-manager tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from postgres_manager.config import AppConfig, DatabaseConfig, InstanceConfig


@pytest.fixture()
def instance1() -> InstanceConfig:
    """Return a test InstanceConfig for instance 1."""
    return InstanceConfig(
        cluster_name="main1",
        port=5432,
        admin_user="pgadmin1",
        data_dir="/var/lib/postgresql/18/main1",
        socket_dir="/var/run/postgresql",
    )


@pytest.fixture()
def instance2() -> InstanceConfig:
    """Return a test InstanceConfig for instance 2."""
    return InstanceConfig(
        cluster_name="main2",
        port=5433,
        admin_user="pgadmin2",
        data_dir="/var/lib/postgresql/18/main2",
        socket_dir="/var/run/postgresql",
    )


@pytest.fixture()
def database_config() -> DatabaseConfig:
    """Return a test DatabaseConfig."""
    return DatabaseConfig(name="demodb", table_name="demo")


@pytest.fixture()
def app_config(
    instance1: InstanceConfig,
    instance2: InstanceConfig,
    database_config: DatabaseConfig,
) -> AppConfig:
    """Return a test AppConfig."""
    return AppConfig(
        pg_version=18,
        instance1=instance1,
        instance2=instance2,
        database=database_config,
    )


@pytest.fixture()
def config_toml_path(tmp_path: Path) -> Path:
    """Create a temporary config.toml and return its path."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[postgres]
version = 18

[instance1]
cluster_name = "main1"
port = 5432
admin_user = "pgadmin1"
data_dir = "/var/lib/postgresql/18/main1"
socket_dir = "/var/run/postgresql"

[instance2]
cluster_name = "main2"
port = 5433
admin_user = "pgadmin2"
data_dir = "/var/lib/postgresql/18/main2"
socket_dir = "/var/run/postgresql"

[database]
name = "demodb"

[table]
name = "demo"
"""
    )
    return config
