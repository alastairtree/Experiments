"""Tests for KeycloakManager."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pytest_keycloak.exceptions import (
    JavaNotFoundError,
    KeycloakDownloadError,
    KeycloakStartError,
    KeycloakTimeoutError,
)
from pytest_keycloak.manager import KeycloakManager


class TestKeycloakManager:
    """Test cases for KeycloakManager."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        manager = KeycloakManager()

        assert manager.version == "26.0.7"
        assert manager.port == 8080
        assert manager.admin_user == "admin"
        assert manager.admin_password == "admin"
        assert manager.install_dir == Path.home() / ".keycloak-test"
        assert manager.keycloak_dir == manager.install_dir / "keycloak-26.0.7"

    def test_init_custom_values(self, tmp_path):
        """Test initialization with custom values."""
        manager = KeycloakManager(
            version="25.0.0",
            install_dir=tmp_path,
            port=9090,
            admin_user="custom_admin",
            admin_password="custom_pass",
        )

        assert manager.version == "25.0.0"
        assert manager.port == 9090
        assert manager.admin_user == "custom_admin"
        assert manager.admin_password == "custom_pass"
        assert manager.install_dir == tmp_path
        assert manager.keycloak_dir == tmp_path / "keycloak-25.0.0"

    @patch("subprocess.run")
    def test_check_java_version_success(self, mock_run):
        """Test successful Java version check."""
        mock_run.return_value = Mock(
            stdout="",
            stderr='openjdk version "17.0.1"',
        )

        manager = KeycloakManager()
        assert manager.check_java_version() is True

    @patch("subprocess.run")
    def test_check_java_version_older_version(self, mock_run):
        """Test Java version check with older version."""
        mock_run.return_value = Mock(
            stdout="",
            stderr='java version "11.0.1"',
        )

        manager = KeycloakManager()
        with pytest.raises(JavaNotFoundError, match="Java 11 found"):
            manager.check_java_version()

    @patch("subprocess.run")
    def test_check_java_version_not_found(self, mock_run):
        """Test Java version check when Java is not installed."""
        mock_run.side_effect = FileNotFoundError()

        manager = KeycloakManager()
        with pytest.raises(JavaNotFoundError, match="Java not found"):
            manager.check_java_version()

    def test_get_base_url(self):
        """Test get_base_url method."""
        manager = KeycloakManager(port=8081)
        assert manager.get_base_url() == "http://localhost:8081"

    def test_is_running_no_process(self):
        """Test is_running when no process exists."""
        manager = KeycloakManager()
        assert manager.is_running() is False

    def test_is_running_with_running_process(self):
        """Test is_running with a running process."""
        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.poll.return_value = None  # Process still running

        assert manager.is_running() is True

    def test_is_running_with_terminated_process(self):
        """Test is_running with a terminated process."""
        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.poll.return_value = 0  # Process terminated

        assert manager.is_running() is False

    @patch("subprocess.run")
    @patch("zipfile.ZipFile")
    @patch("requests.get")
    @patch("pathlib.Path.exists")
    def test_download_and_install_already_installed(
        self, mock_exists, mock_get, mock_zipfile, mock_run
    ):
        """Test download_and_install when already installed."""
        mock_run.return_value = Mock(stdout="", stderr='openjdk version "17.0.1"')
        mock_exists.return_value = True

        manager = KeycloakManager()
        manager.download_and_install()

        # Should not download if already exists
        mock_get.assert_not_called()

    @patch("subprocess.run")
    @patch("requests.get")
    def test_download_and_install_java_not_found(self, mock_get, mock_run):
        """Test download_and_install when Java is not found."""
        mock_run.side_effect = FileNotFoundError()

        manager = KeycloakManager()
        with pytest.raises(JavaNotFoundError):
            manager.download_and_install()

    @patch("subprocess.run")
    @patch("requests.get")
    @patch("pathlib.Path.exists")
    def test_download_and_install_download_failure(self, mock_exists, mock_get, mock_run):
        """Test download_and_install when download fails."""
        mock_run.return_value = Mock(stdout="", stderr='openjdk version "17.0.1"')
        mock_exists.return_value = False
        mock_get.side_effect = Exception("Network error")

        manager = KeycloakManager()
        with pytest.raises(KeycloakDownloadError, match="Installation failed"):
            manager.download_and_install()

    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    def test_start_not_installed(self, mock_exists, mock_popen):
        """Test start when Keycloak is not installed."""
        mock_exists.return_value = False

        manager = KeycloakManager()
        with pytest.raises(KeycloakStartError, match="not installed"):
            manager.start()

    def test_stop_not_running(self):
        """Test stop when Keycloak is not running."""
        manager = KeycloakManager()
        # Should not raise an error
        manager.stop()

    def test_stop_graceful_shutdown(self):
        """Test graceful shutdown."""
        manager = KeycloakManager()
        manager.process = MagicMock()

        manager.stop(timeout=5)

        manager.process.terminate.assert_called_once()
        manager.process.wait.assert_called_once()
        assert manager.process is None

    def test_stop_force_kill(self):
        """Test force kill when graceful shutdown times out."""
        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

        manager.stop(timeout=1)

        manager.process.terminate.assert_called_once()
        manager.process.kill.assert_called_once()

    @patch("requests.get")
    def test_wait_for_ready_success(self, mock_get):
        """Test wait_for_ready when server becomes ready."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.poll.return_value = None

        # Should not raise
        manager.wait_for_ready(timeout=5)

    @patch("requests.get")
    @patch("time.sleep")
    def test_wait_for_ready_timeout(self, mock_sleep, mock_get):
        """Test wait_for_ready when timeout occurs."""
        mock_get.side_effect = Exception("Connection refused")

        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.poll.return_value = None
        manager.log_file = Path("/tmp/test.log")

        with pytest.raises(KeycloakTimeoutError, match="did not become ready"):
            manager.wait_for_ready(timeout=1)

    @patch("requests.get")
    def test_wait_for_ready_process_terminated(self, mock_get):
        """Test wait_for_ready when process terminates."""
        mock_get.side_effect = Exception("Connection refused")

        manager = KeycloakManager()
        manager.process = MagicMock()
        manager.process.poll.return_value = 1  # Process terminated
        manager.log_file = Path("/tmp/test.log")

        with pytest.raises(KeycloakTimeoutError, match="process terminated"):
            manager.wait_for_ready(timeout=5)

    def test_cleanup(self):
        """Test cleanup method."""
        manager = KeycloakManager()
        manager.process = MagicMock()

        manager.cleanup()

        # Should stop the server
        manager.process.terminate.assert_called_once()
