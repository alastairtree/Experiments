"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from postgres_manager.config import (
    AppConfig,
    DatabaseConfig,
    InstanceConfig,
    get_connection_string,
    load_config,
)


class TestLoadConfig:
    """Tests for load_config()."""

    def test_loads_valid_config(self, config_toml_path: Path) -> None:
        """Config is loaded correctly from a valid TOML file."""
        cfg = load_config(config_toml_path)

        assert isinstance(cfg, AppConfig)
        assert cfg.pg_version == 18

    def test_instance1_fields(self, config_toml_path: Path) -> None:
        """Instance 1 fields are parsed correctly."""
        cfg = load_config(config_toml_path)

        assert cfg.instance1.cluster_name == "main1"
        assert cfg.instance1.port == 5432
        assert cfg.instance1.admin_user == "pgadmin1"
        assert cfg.instance1.data_dir == "/var/lib/postgresql/18/main1"
        assert cfg.instance1.socket_dir == "/var/run/postgresql"

    def test_instance2_fields(self, config_toml_path: Path) -> None:
        """Instance 2 fields are parsed correctly."""
        cfg = load_config(config_toml_path)

        assert cfg.instance2.cluster_name == "main2"
        assert cfg.instance2.port == 5433
        assert cfg.instance2.admin_user == "pgadmin2"

    def test_database_config(self, config_toml_path: Path) -> None:
        """Database and table names are parsed correctly."""
        cfg = load_config(config_toml_path)

        assert cfg.database.name == "demodb"
        assert cfg.database.table_name == "demo"

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised when the config file does not exist."""
        missing = tmp_path / "does_not_exist.toml"
        with pytest.raises(FileNotFoundError, match="does_not_exist.toml"):
            load_config(missing)

    def test_raises_on_missing_key(self, tmp_path: Path) -> None:
        """KeyError is raised when a required key is absent."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[postgres]\nversion = 18\n")  # missing instance1 etc.
        with pytest.raises(KeyError):
            load_config(bad_config)

    def test_uses_default_path_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config() uses DEFAULT_CONFIG_PATH when no path is provided."""
        import postgres_manager.config as cfg_module

        fake_path = Path("/tmp/fake_config.toml")

        def mock_load(p: Path | None = None) -> AppConfig:
            raise FileNotFoundError(str(p))

        monkeypatch.setattr(cfg_module, "load_config", mock_load)
        with pytest.raises(FileNotFoundError):
            cfg_module.load_config(None)


class TestGetConnectionString:
    """Tests for get_connection_string()."""

    def test_builds_correct_string(self, instance1: InstanceConfig) -> None:
        """Connection string contains expected host, port, user and dbname."""
        conn_str = get_connection_string(instance1, "secret")

        assert "host=localhost" in conn_str
        assert "port=5432" in conn_str
        assert "user=pgadmin1" in conn_str
        assert "password=secret" in conn_str
        assert "dbname=postgres" in conn_str

    def test_custom_database(self, instance1: InstanceConfig) -> None:
        """A custom database name is included in the connection string."""
        conn_str = get_connection_string(instance1, "secret", database="demodb")

        assert "dbname=demodb" in conn_str

    def test_instances_have_different_ports(
        self,
        instance1: InstanceConfig,
        instance2: InstanceConfig,
    ) -> None:
        """Connection strings for the two instances use different ports."""
        conn1 = get_connection_string(instance1, "pw1")
        conn2 = get_connection_string(instance2, "pw2")

        assert "port=5432" in conn1
        assert "port=5433" in conn2


class TestInstanceConfig:
    """Tests for InstanceConfig dataclass."""

    def test_instances_have_different_cluster_names(
        self,
        instance1: InstanceConfig,
        instance2: InstanceConfig,
    ) -> None:
        """The two default instances use distinct cluster names."""
        assert instance1.cluster_name != instance2.cluster_name

    def test_instances_have_different_admin_users(
        self,
        instance1: InstanceConfig,
        instance2: InstanceConfig,
    ) -> None:
        """The two default instances have distinct admin user names."""
        assert instance1.admin_user != instance2.admin_user

    def test_instances_have_different_ports(
        self,
        instance1: InstanceConfig,
        instance2: InstanceConfig,
    ) -> None:
        """The two default instances use distinct TCP ports."""
        assert instance1.port != instance2.port
