"""Unit tests for configuration loading — no database required."""

from __future__ import annotations

from pathlib import Path

import pytest

from postgres_manager.config import (
    AppConfig,
    DatabaseConfig,
    InstanceConfig,
    get_connection_string,
    load_config,
    resolve_instance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(content)
    return p


VALID_TWO_INSTANCE_TOML = """
[postgres]
version = 18

[[instances]]
cluster_name = "main1"
port = 5432
admin_user = "pgadmin1"
socket_dir = "/var/run/postgresql"

[[instances]]
cluster_name = "main2"
port = 5433
admin_user = "pgadmin2"
socket_dir = "/var/run/postgresql"

[database]
name = "demodb"

[table]
name = "demo"
"""

VALID_ONE_INSTANCE_TOML = """
[postgres]
version = 18

[[instances]]
cluster_name = "solo"
port = 5432
admin_user = "admin"

[database]
name = "mydb"

[table]
name = "mytable"
"""


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_two_instances(self, tmp_path: Path) -> None:
        cfg = load_config(_write_config(tmp_path, VALID_TWO_INSTANCE_TOML))
        assert cfg.pg_version == 18
        assert len(cfg.instances) == 2

    def test_instance_fields(self, tmp_path: Path) -> None:
        cfg = load_config(_write_config(tmp_path, VALID_TWO_INSTANCE_TOML))
        i1, i2 = cfg.instances
        assert i1.cluster_name == "main1"
        assert i1.port == 5432
        assert i1.admin_user == "pgadmin1"
        assert i2.cluster_name == "main2"
        assert i2.port == 5433

    def test_database_and_table(self, tmp_path: Path) -> None:
        cfg = load_config(_write_config(tmp_path, VALID_TWO_INSTANCE_TOML))
        assert cfg.database.name == "demodb"
        assert cfg.database.table_name == "demo"

    def test_socket_dir_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(_write_config(tmp_path, VALID_ONE_INSTANCE_TOML))
        assert cfg.instances[0].socket_dir == "/var/run/postgresql"

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "missing.toml")

    def test_raises_on_missing_key(self, tmp_path: Path) -> None:
        bad = _write_config(tmp_path, "[postgres]\nversion = 18\n")
        with pytest.raises((KeyError, TypeError)):
            load_config(bad)

    def test_raises_on_empty_instances(self, tmp_path: Path) -> None:
        bad = _write_config(
            tmp_path,
            "[postgres]\nversion=18\n[database]\nname='d'\n[table]\nname='t'\n",
        )
        with pytest.raises((KeyError, TypeError, ValueError)):
            load_config(bad)


# ---------------------------------------------------------------------------
# resolve_instance
# ---------------------------------------------------------------------------


class TestResolveInstance:
    def _cfg(self, tmp_path: Path, toml: str) -> AppConfig:
        return load_config(_write_config(tmp_path, toml))

    def test_auto_select_single_instance(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_ONE_INSTANCE_TOML)
        inst = resolve_instance(cfg, None)
        assert inst.cluster_name == "solo"

    def test_error_when_multiple_and_none_given(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_TWO_INSTANCE_TOML)
        with pytest.raises(ValueError, match="Specify one"):
            resolve_instance(cfg, None)

    def test_select_by_cluster_name(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_TWO_INSTANCE_TOML)
        assert resolve_instance(cfg, "main2").port == 5433

    def test_select_by_1_based_index(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_TWO_INSTANCE_TOML)
        assert resolve_instance(cfg, "1").cluster_name == "main1"
        assert resolve_instance(cfg, "2").cluster_name == "main2"

    def test_error_on_unknown_name(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_TWO_INSTANCE_TOML)
        with pytest.raises(ValueError, match="not found"):
            resolve_instance(cfg, "nope")

    def test_error_on_out_of_range_index(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path, VALID_TWO_INSTANCE_TOML)
        with pytest.raises(ValueError):
            resolve_instance(cfg, "99")


# ---------------------------------------------------------------------------
# get_connection_string
# ---------------------------------------------------------------------------


class TestGetConnectionString:
    def _inst(self) -> InstanceConfig:
        return InstanceConfig(
            cluster_name="main1",
            port=5432,
            admin_user="pgadmin1",
            socket_dir="/var/run/postgresql",
        )

    def test_contains_expected_fields(self) -> None:
        s = get_connection_string(self._inst(), "secret")
        assert "host=localhost" in s
        assert "port=5432" in s
        assert "user=pgadmin1" in s
        assert "password=secret" in s
        assert "dbname=postgres" in s

    def test_custom_database(self) -> None:
        s = get_connection_string(self._inst(), "secret", database="demodb")
        assert "dbname=demodb" in s
