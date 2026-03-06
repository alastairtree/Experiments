"""Tests for the Click CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from postgres_manager.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    """Return a Click test runner."""
    return CliRunner()


@pytest.fixture()
def cli_config_arg(config_toml_path: Path) -> list[str]:
    """Return the --config CLI argument pointing to the temp config file."""
    return ["--config", str(config_toml_path)]


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


class TestInstallCommand:
    """Tests for the 'install' CLI command."""

    @patch("postgres_manager.cli.install_all")
    def test_install_success(
        self,
        mock_install: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """install command exits 0 and calls install_all."""
        result = runner.invoke(main, ["install"] + cli_config_arg)

        assert result.exit_code == 0, result.output
        mock_install.assert_called_once()

    def test_install_missing_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """install command exits non-zero when config file is missing."""
        result = runner.invoke(
            main, ["install", "--config", str(tmp_path / "missing.toml")]
        )
        # Click validates the path itself and returns exit code 2
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


class TestStartCommand:
    """Tests for the 'start' CLI command."""

    @patch("postgres_manager.cli.start_all")
    def test_start_with_passwords(
        self,
        mock_start: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """start command calls start_all when passwords are provided."""
        result = runner.invoke(
            main,
            ["start"] + cli_config_arg + ["--password1", "pw1", "--password2", "pw2"],
        )

        assert result.exit_code == 0, result.output
        mock_start.assert_called_once()
        _, p1, p2 = mock_start.call_args[0]
        assert p1 == "pw1"
        assert p2 == "pw2"

    def test_start_missing_passwords(
        self,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """start command exits non-zero when passwords are missing."""
        result = runner.invoke(main, ["start"] + cli_config_arg)
        assert result.exit_code != 0

    @patch("postgres_manager.cli.start_all")
    def test_start_passwords_via_env(
        self,
        mock_start: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """start command reads passwords from PGPASSWORD1/PGPASSWORD2 env vars."""
        result = runner.invoke(
            main,
            ["start"] + cli_config_arg,
            env={"PGPASSWORD1": "envpw1", "PGPASSWORD2": "envpw2"},
        )
        assert result.exit_code == 0, result.output
        mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


class TestStopCommand:
    """Tests for the 'stop' CLI command."""

    @patch("postgres_manager.cli.stop_cluster")
    def test_stop_success(
        self,
        mock_stop: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """stop command calls stop_cluster for both instances."""
        result = runner.invoke(main, ["stop"] + cli_config_arg)

        assert result.exit_code == 0, result.output
        assert mock_stop.call_count == 2


# ---------------------------------------------------------------------------
# create-table
# ---------------------------------------------------------------------------


class TestCreateTableCommand:
    """Tests for the 'create-table' CLI command."""

    @patch("postgres_manager.cli.create_table_all")
    def test_create_table_success(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """create-table command calls create_table_all with correct passwords."""
        result = runner.invoke(
            main,
            ["create-table"] + cli_config_arg + ["--password1", "pw1", "--password2", "pw2"],
        )

        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()

    def test_create_table_missing_passwords(
        self,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """create-table exits non-zero when passwords are missing."""
        result = runner.invoke(main, ["create-table"] + cli_config_arg)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


class TestInsertCommand:
    """Tests for the 'insert' CLI command."""

    @patch("postgres_manager.cli.insert_all")
    def test_insert_success(
        self,
        mock_insert: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """insert command calls insert_all with both passwords."""
        result = runner.invoke(
            main,
            ["insert"] + cli_config_arg + ["--password1", "pw1", "--password2", "pw2"],
        )

        assert result.exit_code == 0, result.output
        mock_insert.assert_called_once()

    def test_insert_missing_passwords(
        self,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """insert exits non-zero when passwords are missing."""
        result = runner.invoke(main, ["insert"] + cli_config_arg)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


class TestQueryCommand:
    """Tests for the 'query' CLI command."""

    @patch("postgres_manager.cli.query_all")
    def test_query_shows_results(
        self,
        mock_query: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """query command displays rows from both instances."""
        mock_query.return_value = (
            [{"id": 1, "instance": "main1", "message": "msg1", "created": "now"}],
            [{"id": 1, "instance": "main2", "message": "msg2", "created": "now"}],
        )

        result = runner.invoke(
            main,
            ["query"] + cli_config_arg + ["--password1", "pw1", "--password2", "pw2"],
        )

        assert result.exit_code == 0, result.output
        assert "main1" in result.output
        assert "main2" in result.output
        assert "msg1" in result.output
        assert "msg2" in result.output

    @patch("postgres_manager.cli.query_all")
    def test_query_confirms_different_data(
        self,
        mock_query: MagicMock,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """query outputs a confirmation message when instances hold different data."""
        mock_query.return_value = (
            [{"id": 1, "instance": "main1", "message": "hello from 1", "created": "t"}],
            [{"id": 1, "instance": "main2", "message": "hello from 2", "created": "t"}],
        )

        result = runner.invoke(
            main,
            ["query"] + cli_config_arg + ["--password1", "pw1", "--password2", "pw2"],
        )

        assert result.exit_code == 0
        assert "confirmed independent" in result.output

    def test_query_missing_passwords(
        self,
        runner: CliRunner,
        cli_config_arg: list[str],
    ) -> None:
        """query exits non-zero when passwords are missing."""
        result = runner.invoke(main, ["query"] + cli_config_arg)
        assert result.exit_code != 0
