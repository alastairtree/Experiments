"""Tests for the 'connect' CLI command and related helpers.

These tests do NOT require a running PostgreSQL instance — they exercise
the interactive wizard, TOML generation, and default-path logic only.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner
from click.testing import Result

from postgres_manager.cli import _build_toml, _prompt_instance, main
from postgres_manager.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PLAN_PATH,
    InstanceConfig,
    ReplicationConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke(runner: CliRunner, args: list[str], input: str = "") -> Result:
    return runner.invoke(main, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# _build_toml unit tests
# ---------------------------------------------------------------------------


class TestBuildToml:
    def _pub(self) -> InstanceConfig:
        return InstanceConfig(
            cluster_name="pub1",
            port=5432,
            admin_user="pgadmin",
            socket_dir="/var/run/postgresql",
        )

    def _sub(self) -> InstanceConfig:
        return InstanceConfig(
            cluster_name="sub1",
            port=5433,
            admin_user="pgadmin2",
            socket_dir="/var/run/postgresql",
        )

    def test_basic_structure_is_valid_toml(self) -> None:
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", None)
        data = tomllib.loads(content)
        assert data["postgres"]["version"] == 16
        assert len(data["instances"]) == 2

    def test_publisher_fields(self) -> None:
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", None)
        data = tomllib.loads(content)
        pub = data["instances"][0]
        assert pub["cluster_name"] == "pub1"
        assert pub["port"] == 5432
        assert pub["admin_user"] == "pgadmin"
        assert pub["socket_dir"] == "/var/run/postgresql"

    def test_subscriber_fields(self) -> None:
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", None)
        data = tomllib.loads(content)
        sub = data["instances"][1]
        assert sub["cluster_name"] == "sub1"
        assert sub["port"] == 5433
        assert sub["admin_user"] == "pgadmin2"

    def test_database_section(self) -> None:
        content = _build_toml(16, self._pub(), self._sub(), "testdb", "mytable", None)
        data = tomllib.loads(content)
        assert data["database"]["name"] == "testdb"
        assert data["table"]["name"] == "mytable"

    def test_no_replication_section_when_none(self) -> None:
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", None)
        data = tomllib.loads(content)
        assert "replication" not in data

    def test_replication_section_included(self) -> None:
        rep = ReplicationConfig(
            publisher_instance="pub1",
            subscriber_instance="sub1",
            publication_name="my_pub",
            subscription_name="my_sub",
            replication_user="replicator",
        )
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", rep)
        data = tomllib.loads(content)
        assert data["replication"]["publisher_instance"] == "pub1"
        assert data["replication"]["subscriber_instance"] == "sub1"
        assert data["replication"]["publication_name"] == "my_pub"
        assert data["replication"]["subscription_name"] == "my_sub"
        assert data["replication"]["replication_user"] == "replicator"

    def test_replication_tables_included(self) -> None:
        from postgres_manager.config import TableReplicationEntry
        rep = ReplicationConfig(
            publisher_instance="pub1",
            subscriber_instance="sub1",
            publication_name="p",
            subscription_name="s",
            replication_user="r",
            tables=[
                TableReplicationEntry(schema="public", name="orders", status="exists"),
            ],
        )
        content = _build_toml(16, self._pub(), self._sub(), "mydb", "demo", rep)
        data = tomllib.loads(content)
        tables = data["replication"]["tables"]
        assert len(tables) == 1
        assert tables[0]["name"] == "orders"
        assert tables[0]["schema"] == "public"
        assert tables[0]["status"] == "exists"

    def test_different_pg_versions(self) -> None:
        for version in (14, 15, 16, 17):
            content = _build_toml(version, self._pub(), self._sub(), "db", "t", None)
            data = tomllib.loads(content)
            assert data["postgres"]["version"] == version


# ---------------------------------------------------------------------------
# connect command — field-by-field flow
# ---------------------------------------------------------------------------


class TestConnectCommandFieldByField:
    def test_creates_config_file(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        # Simulate: version=16, publisher (no URI, host=dbhost, port=5432, user=admin,
        # cluster=pub1, socket=/var/run/postgresql), subscriber (similar),
        # db=testdb, table=demo, no replication
        user_input = "\n".join([
            "16",       # pg version
            "n",        # publisher: no connection string
            "dbhost",   # host
            "5432",     # port
            "admin",    # user
            "pub1",     # cluster_name
            "/var/run/postgresql",  # socket_dir
            "n",        # subscriber: no connection string
            "dbhost2",  # host
            "5433",     # port
            "admin2",   # user
            "sub1",     # cluster_name
            "/var/run/postgresql",  # socket_dir
            "testdb",   # db name
            "demo",     # table name
            "n",        # no replication config
        ]) + "\n"
        result = _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        assert result.exit_code == 0, result.output
        assert out.exists()

    def test_config_file_is_valid_toml(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "localhost", "5432", "pgadmin", "main1",
            "/var/run/postgresql",
            "n", "localhost", "5433", "pgadmin2", "main2",
            "/var/run/postgresql",
            "appdb", "events", "n",
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        data = tomllib.loads(out.read_text())
        assert data["postgres"]["version"] == 16
        assert data["database"]["name"] == "appdb"
        assert data["table"]["name"] == "events"

    def test_instances_saved_correctly(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "pghost1", "15432", "dba1", "cluster_a",
            "/tmp/pg1",
            "n", "pghost2", "15433", "dba2", "cluster_b",
            "/tmp/pg2",
            "proddb", "logs", "n",
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        data = tomllib.loads(out.read_text())
        assert data["instances"][0]["cluster_name"] == "cluster_a"
        assert data["instances"][0]["port"] == 15432
        assert data["instances"][0]["admin_user"] == "dba1"
        assert data["instances"][0]["socket_dir"] == "/tmp/pg1"
        assert data["instances"][1]["cluster_name"] == "cluster_b"
        assert data["instances"][1]["port"] == 15433

    def test_with_replication_config(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "localhost", "5432", "admin", "pub",
            "/var/run/postgresql",
            "n", "localhost", "5433", "admin", "sub",
            "/var/run/postgresql",
            "mydb", "demo",
            "y",            # yes, configure replication
            "pub_pub",      # publication name
            "sub_sub",      # subscription name
            "replicator",   # replication user
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        data = tomllib.loads(out.read_text())
        assert data["replication"]["publication_name"] == "pub_pub"
        assert data["replication"]["subscription_name"] == "sub_sub"
        assert data["replication"]["replication_user"] == "replicator"
        assert data["replication"]["publisher_instance"] == "pub"
        assert data["replication"]["subscriber_instance"] == "sub"

    def test_output_shows_config_path(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "localhost", "5432", "admin", "main1",
            "/var/run/postgresql",
            "n", "localhost", "5433", "admin", "main2",
            "/var/run/postgresql",
            "mydb", "demo", "n",
        ]) + "\n"
        result = _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        assert str(out) in result.output

    def test_default_values_accepted(self, tmp_path: Path) -> None:
        """Pressing Enter for all prompts should use sensible defaults."""
        out = tmp_path / "config.toml"
        runner = CliRunner()
        # All empty = accept defaults; we still need 2 cluster names since
        # the prompt has no default overlap issue
        user_input = "\n".join([
            "",     # pg version -> 16
            "n",    # publisher: no URI
            "",     # host -> localhost
            "",     # port -> 5432
            "",     # user -> postgres
            "main1",  # cluster name (needs something unique)
            "",     # socket_dir -> /var/run/postgresql
            "n",    # subscriber: no URI
            "",     # host -> localhost
            "",     # port -> 5432
            "",     # user -> postgres
            "main2",  # cluster name
            "",     # socket_dir -> /var/run/postgresql
            "",     # db -> mydb
            "",     # table -> demo
            "n",    # no replication
        ]) + "\n"
        result = _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        assert result.exit_code == 0, result.output
        data = tomllib.loads(out.read_text())
        assert data["postgres"]["version"] == 16
        assert data["database"]["name"] == "mydb"
        assert data["table"]["name"] == "demo"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "dir" / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "localhost", "5432", "admin", "main1",
            "/var/run/postgresql",
            "n", "localhost", "5433", "admin", "main2",
            "/var/run/postgresql",
            "mydb", "demo", "n",
        ]) + "\n"
        result = _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        assert result.exit_code == 0, result.output
        assert out.exists()


# ---------------------------------------------------------------------------
# connect command — connection string flow
# ---------------------------------------------------------------------------


class TestConnectCommandConnectionString:
    def test_uri_parsed_for_publisher(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16",
            "y",    # publisher: use connection string
            "postgresql://dbowner@pgserver1:9999/appdb",
            "pub_cluster",          # cluster name
            "/var/run/postgresql",  # socket dir
            "n",    # subscriber: no URI
            "localhost", "5433", "admin", "sub_cluster",
            "/var/run/postgresql",
            "appdb", "records", "n",
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        data = tomllib.loads(out.read_text())
        pub = data["instances"][0]
        assert pub["port"] == 9999
        assert pub["admin_user"] == "dbowner"
        assert pub["cluster_name"] == "pub_cluster"

    def test_uri_parsed_for_subscriber(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16",
            "n",    # publisher: no URI
            "localhost", "5432", "admin", "pub_cluster",
            "/var/run/postgresql",
            "y",    # subscriber: use connection string
            "postgresql://repuser@slave.example.com:5434/replicadb",
            "sub_cluster",
            "/var/run/postgresql",
            "replicadb", "data", "n",
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        data = tomllib.loads(out.read_text())
        sub = data["instances"][1]
        assert sub["port"] == 5434
        assert sub["admin_user"] == "repuser"
        assert sub["cluster_name"] == "sub_cluster"

    def test_both_uri(self, tmp_path: Path) -> None:
        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16",
            "y",
            "postgresql://alice@host1:6001/db",
            "alice_cluster",
            "/var/run/postgresql",
            "y",
            "postgresql://bob@host2:6002/db",
            "bob_cluster",
            "/var/run/postgresql",
            "db", "t",
            "y",
            "",  # default pub name
            "",  # default sub name
            "",  # default replication user
        ]) + "\n"
        result = _invoke(runner, ["connect", "--output", str(out)], input=user_input)
        assert result.exit_code == 0, result.output
        data = tomllib.loads(out.read_text())
        assert data["instances"][0]["port"] == 6001
        assert data["instances"][1]["port"] == 6002
        assert data["instances"][0]["admin_user"] == "alice"
        assert data["instances"][1]["admin_user"] == "bob"


# ---------------------------------------------------------------------------
# Default path constants
# ---------------------------------------------------------------------------


class TestDefaultPaths:
    def test_default_config_path_in_home_dir(self) -> None:
        home = Path.home()
        assert DEFAULT_CONFIG_PATH.is_relative_to(home)

    def test_default_config_path_named_config_toml(self) -> None:
        assert DEFAULT_CONFIG_PATH.name == "config.toml"

    def test_default_plan_path_in_home_dir(self) -> None:
        home = Path.home()
        assert DEFAULT_PLAN_PATH.is_relative_to(home)

    def test_default_plan_path_named_replication_plan(self) -> None:
        assert DEFAULT_PLAN_PATH.name == "replication-plan.json"

    def test_both_in_same_product_dir(self) -> None:
        assert DEFAULT_CONFIG_PATH.parent == DEFAULT_PLAN_PATH.parent

    def test_product_dir_named_postgres_manager(self) -> None:
        assert DEFAULT_CONFIG_PATH.parent.name == ".postgres-manager"

    def test_loaded_config_matches_path(self, tmp_path: Path) -> None:
        """Config written by connect can be loaded by load_config."""
        from postgres_manager.config import load_config

        out = tmp_path / "config.toml"
        runner = CliRunner()
        user_input = "\n".join([
            "16", "n", "localhost", "5432", "admin", "pub",
            "/var/run/postgresql",
            "n", "localhost", "5433", "admin", "sub",
            "/var/run/postgresql",
            "appdb", "events", "n",
        ]) + "\n"
        _invoke(runner, ["connect", "--output", str(out)], input=user_input)

        cfg = load_config(out)
        assert cfg.pg_version == 16
        assert len(cfg.instances) == 2
        assert cfg.database.name == "appdb"
        assert cfg.instances[0].cluster_name == "pub"
        assert cfg.instances[1].cluster_name == "sub"
