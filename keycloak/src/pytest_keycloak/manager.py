"""Keycloak lifecycle management."""

import atexit
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Dict, Optional

import requests

from .exceptions import (
    JavaNotFoundError,
    KeycloakDownloadError,
    KeycloakStartError,
    KeycloakTimeoutError,
)

logger = logging.getLogger(__name__)


class KeycloakManager:
    """
    Manages the lifecycle of a local Keycloak instance.

    Responsibilities:
    - Download and extract Keycloak
    - Start/stop the server
    - Manage realm configuration
    - Health checks
    """

    _lock = Lock()
    _instances: list["KeycloakManager"] = []  # Track all instances globally

    def __init__(
        self,
        version: str = "26.0.7",
        install_dir: Optional[Path] = None,
        port: Optional[int] = None,
        admin_user: str = "admin",
        admin_password: str = "admin",
        management_port: Optional[int] = None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize KeycloakManager.

        Before creating a new instance, any existing running instances will be stopped.

        Args:
            version: Keycloak version to download
            install_dir: Where to install Keycloak (default: ~/.keycloak-test)
            port: HTTP port for Keycloak (default: auto-select from 8080+)
            admin_user: Admin username
            admin_password: Admin password
            management_port: Management/health port (default: port + 1000)
            data_dir: Directory for instance data and logs (default: auto-generated timestamped directory)
        """
        # Stop any existing running instances before creating a new one
        with self._lock:
            for instance in self._instances[:]:  # Use a copy to avoid modification during iteration
                if instance.is_running():
                    logger.info(
                        f"Stopping existing Keycloak instance on port {instance.port} before creating new instance"
                    )
                    instance.stop()
                    # Wait for process to fully terminate
                    max_wait = 10
                    waited = 0
                    while instance.is_running() and waited < max_wait:
                        time.sleep(0.5)
                        waited += 0.5
                    if instance.is_running():
                        logger.warning(
                            f"Existing instance on port {instance.port} did not stop within {max_wait}s"
                        )

        self.version = version
        self.install_dir = install_dir or Path.home() / ".keycloak-test"
        self._explicit_port = port is not None or management_port is not None
        self.port = port if port is not None else 8080
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.management_port = management_port if management_port is not None else self.port + 1000

        # Generate timestamped data directory if not provided
        if data_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.data_dir = Path.cwd() / "keycloak-dev-server" / f"instance_{timestamp}"
        else:
            self.data_dir = Path(data_dir)

        self.keycloak_dir = self.install_dir / f"keycloak-{version}"
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.log_file: Optional[Path] = None
        self.realm_config_file: Optional[Path] = None  # Track realm config file for cleanup
        self._output_thread: Optional[Thread] = None  # Thread for reading process output
        self._backup_dir: Optional[Path] = None  # Backup directory for data/conf

        # Register this instance globally
        with self._lock:
            self._instances.append(self)

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler for atexit."""
        if self.is_running():
            try:
                self.stop()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

        # Remove from global instances list
        with self._lock:
            if self in self._instances:
                self._instances.remove(self)

    @classmethod
    def stop_all_instances(cls) -> None:
        """
        Stop all running Keycloak instances.

        This is useful for test teardown or cleanup.
        """
        with cls._lock:
            instances_to_stop = cls._instances[:]  # Create a copy
            for instance in instances_to_stop:
                if instance.is_running():
                    logger.info(f"Stopping Keycloak instance on port {instance.port}")
                    try:
                        instance.stop()
                    except Exception as e:
                        logger.warning(f"Error stopping instance on port {instance.port}: {e}")

    @classmethod
    def get_running_instances_count(cls) -> int:
        """
        Get the count of currently running Keycloak instances.

        Returns:
            Number of running instances
        """
        with cls._lock:
            return sum(1 for instance in cls._instances if instance.is_running())

    def _read_output(self, pipe, prefix: str = "") -> None:
        """
        Read output from a subprocess pipe and log it.

        Args:
            pipe: The pipe to read from (stdout or stderr)
            prefix: Optional prefix for log messages
        """
        try:
            for line in iter(pipe.readline, b""):
                if line:
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if decoded:
                        logger.info(f"{prefix}{decoded}")
        except Exception as e:
            logger.debug(f"Error reading output: {e}")
        finally:
            pipe.close()

    def _backup_directories(self) -> None:
        """
        Backup the data/ and conf/ directories before starting Keycloak.

        This ensures we can restore to a clean state after stopping.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S_%f")
        self._backup_dir = self.data_dir / f"backup_{timestamp}"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup data directory if it exists
        data_dir = self.keycloak_dir / "data"
        if data_dir.exists():
            backup_data = self._backup_dir / "data"
            shutil.copytree(data_dir, backup_data)
            logger.debug(f"Backed up data directory to {backup_data}")

        # Backup conf directory if it exists
        conf_dir = self.keycloak_dir / "conf"
        if conf_dir.exists():
            backup_conf = self._backup_dir / "conf"
            shutil.copytree(conf_dir, backup_conf)
            logger.debug(f"Backed up conf directory to {backup_conf}")

    def _restore_directories(self) -> None:
        """
        Restore the data/ and conf/ directories from backup.

        This cleans up any changes made during the server run.
        """
        if not self._backup_dir or not self._backup_dir.exists():
            logger.debug("No backup directory to restore from")
            return

        try:
            # Restore data directory
            data_dir = self.keycloak_dir / "data"
            backup_data = self._backup_dir / "data"
            if backup_data.exists():
                # Remove current data directory
                if data_dir.exists():
                    shutil.rmtree(data_dir)
                # Restore from backup
                shutil.copytree(backup_data, data_dir)
                logger.debug("Restored data directory from backup")

            # Restore conf directory
            conf_dir = self.keycloak_dir / "conf"
            backup_conf = self._backup_dir / "conf"
            if backup_conf.exists():
                # Remove current conf directory
                if conf_dir.exists():
                    shutil.rmtree(conf_dir)
                # Restore from backup
                shutil.copytree(backup_conf, conf_dir)
                logger.debug("Restored conf directory from backup")

            # Clean up backup directory
            shutil.rmtree(self._backup_dir)
            logger.debug("Cleaned up backup directory")
            self._backup_dir = None

        except Exception as e:
            logger.warning(f"Failed to restore directories from backup: {e}")

    def check_java_version(self) -> bool:
        """
        Check if Java 17+ is installed.

        Returns:
            True if Java 17+ is available

        Raises:
            JavaNotFoundError: If Java is not installed or version < 17
        """
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stderr + result.stdout

            # Parse version from output like 'openjdk version "17.0.1"'
            version_match = re.search(r'version "(\d+)\.', output)
            if not version_match:
                version_match = re.search(r'version "(\d+)"', output)

            if version_match:
                major_version = int(version_match.group(1))
                if major_version >= 17:
                    return True
                else:
                    raise JavaNotFoundError(f"Java {major_version} found, but Java 17+ is required")
            else:
                raise JavaNotFoundError("Could not parse Java version")

        except FileNotFoundError:
            raise JavaNotFoundError("Java not found. Please install Java 17 or higher")
        except subprocess.TimeoutExpired:
            raise JavaNotFoundError("Java version check timed out")

    def download_and_install(self) -> None:
        """
        Download Keycloak if not already present.

        Steps:
        1. Check if already downloaded (check install_dir/keycloak-{version})
        2. If not, download from GitHub releases
        3. Extract to install_dir
        4. Verify Java installation (>= 17)

        Raises:
            KeycloakDownloadError: If download fails
            JavaNotFoundError: If Java is not installed or wrong version
        """
        # Check Java first
        self.check_java_version()

        # Check if already installed
        if self.keycloak_dir.exists() and (self.keycloak_dir / "bin" / "kc.sh").exists():
            logger.info(f"Keycloak {self.version} already installed at {self.keycloak_dir}")
            return

        logger.info(f"Downloading Keycloak {self.version}...")

        # Create install directory
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # Download URL
        url = (
            f"https://github.com/keycloak/keycloak/releases/download/"
            f"{self.version}/keycloak-{self.version}.zip"
        )

        zip_path = self.install_dir / f"keycloak-{self.version}.zip"

        try:
            # Download with progress
            self._download_with_progress(url, zip_path)

            # Extract
            logger.info(f"Extracting Keycloak to {self.install_dir}...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.install_dir)

            # Make scripts executable on Unix-like systems
            if sys.platform != "win32":
                bin_dir = self.keycloak_dir / "bin"
                for script in bin_dir.glob("*.sh"):
                    script.chmod(0o755)

            logger.info("Keycloak installed successfully")

        except requests.RequestException as e:
            raise KeycloakDownloadError(f"Failed to download Keycloak: {e}")
        except zipfile.BadZipFile as e:
            raise KeycloakDownloadError(f"Downloaded file is not a valid zip: {e}")
        except Exception as e:
            raise KeycloakDownloadError(f"Installation failed: {e}")
        finally:
            # Clean up zip file
            if zip_path.exists():
                zip_path.unlink()

    def _download_with_progress(self, url: str, dest: Path) -> None:
        """
        Download file with progress indication.

        Args:
            url: URL to download from
            dest: Destination file path
        """
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        downloaded = 0
        last_logged_percent = 0

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        # Log only at 5% intervals to avoid excessive logging
                        if percent >= last_logged_percent + 5 or percent >= 100:
                            logger.info(f"Download progress: {percent:.1f}%")
                            last_logged_percent = int(percent / 5) * 5

    def start(
        self,
        realm_config: Optional[Dict[str, Any]] = None,
        wait_for_ready: bool = True,
        timeout: int = 60,
    ) -> None:
        """
        Start the Keycloak server.

        Steps:
        1. Create data/import directory if needed
        2. Write realm_config to data/import/realm.json if provided
        3. Start Keycloak using subprocess
        4. If wait_for_ready, poll health endpoint until ready or timeout

        Args:
            realm_config: Optional realm configuration dict to import
            wait_for_ready: Wait for server to be ready before returning
            timeout: Max seconds to wait for readiness

        Raises:
            KeycloakStartError: If server fails to start
            KeycloakTimeoutError: If server doesn't become ready in time
        """
        with self._lock:
            if self.is_running():
                logger.info("ℹ️  Keycloak is already running, skipping start")
                return

            # Ensure Keycloak is installed
            if not self.keycloak_dir.exists():
                raise KeycloakStartError(
                    "Keycloak is not installed. Call download_and_install() first."
                )

            # Check if requested ports are available
            if self._explicit_port:
                # User specified explicit ports - fail fast if they're in use
                if self._is_port_in_use(self.port):
                    raise KeycloakStartError(
                        f"Port {self.port} is already in use. Please choose a different port."
                    )
                if self._is_port_in_use(self.management_port):
                    raise KeycloakStartError(
                        f"Management port {self.management_port} is already in use. Please choose a different port."
                    )
            else:
                # Auto-select ports starting from default
                http_port, mgmt_port = self._find_available_ports(start_port=self.port)
                if http_port != self.port or mgmt_port != self.management_port:
                    logger.info(
                        f"🔍 Auto-selected available ports: {http_port} (HTTP), {mgmt_port} (management)"
                    )
                    self.port = http_port
                    self.management_port = mgmt_port

            # Prepare realm import if needed
            # Note: Import files must be in data/import, but we use custom DB path
            if realm_config:
                import_dir = self.keycloak_dir / "data" / "import"
                import_dir.mkdir(parents=True, exist_ok=True)

                # Create a unique realm file per port to avoid conflicts
                realm_file = import_dir / f"realm-{self.port}.json"

                with open(realm_file, "w") as f:
                    json.dump(realm_config, f, indent=2)

                # Track the realm config file for cleanup
                self.realm_config_file = realm_file

                realm_name = realm_config.get("realm", "unknown")
                logger.info(f"📝 Configuring Keycloak with realm: {realm_name}")
                logger.info(f"   Realm configuration written to {realm_file}")

            # Create data directory and prepare log file
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.data_dir / "keycloak.log"

            # Prepare environment
            env = os.environ.copy()
            env["KEYCLOAK_ADMIN"] = self.admin_user
            env["KEYCLOAK_ADMIN_PASSWORD"] = self.admin_password

            # Note: We don't set a custom database URL because it causes Liquibase migration
            # errors with H2. The default database location in the Keycloak installation dir
            # is sufficient, as port isolation prevents conflicts between instances.

            # Determine script path
            if sys.platform == "win32":
                script = self.keycloak_dir / "bin" / "kc.bat"
                cmd = [str(script)]
            else:
                script = self.keycloak_dir / "bin" / "kc.sh"
                cmd = [str(script)]

            # Add arguments
            cmd.extend(
                [
                    "start-dev",
                    f"--http-port={self.port}",
                    f"--http-management-port={self.management_port}",
                    "--health-enabled=true",  # Enable health endpoints
                ]
            )

            if realm_config:
                cmd.append("--import-realm")

            logger.info(f"🚀 Starting Keycloak server on port {self.port}...")
            logger.info(f"   Command: {' '.join(cmd)}")

            # Backup data and conf directories before starting
            self._backup_directories()

            try:
                # Start process with piped output so we can log it
                self.process = subprocess.Popen(
                    cmd,
                    cwd=self.keycloak_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,  # Line buffered
                )

                # Start thread to read and log output
                self._output_thread = Thread(
                    target=self._read_output,
                    args=(self.process.stdout, "[Keycloak] "),
                    daemon=True,
                )
                self._output_thread.start()

                # Wait a bit for the process to start
                time.sleep(2)

                # Check if process is still running
                if self.process.poll() is not None:
                    # Process terminated
                    raise KeycloakStartError(
                        f"Keycloak process terminated immediately. Check logs at {self.log_file}"
                    )

                logger.info(f"   Keycloak process started (PID: {self.process.pid})")

                # Wait for readiness
                if wait_for_ready:
                    logger.info(f"   Waiting for Keycloak to be ready (timeout: {timeout}s)...")
                    # Extract realm name if realm_config was provided
                    realm_name = realm_config.get("realm") if realm_config else None
                    self.wait_for_ready(timeout=timeout, realm_name=realm_name)
                    logger.info(f"✅ Keycloak server is ready on http://localhost:{self.port}")

            except Exception as e:
                if self.process:
                    self.process.kill()
                    self.process = None
                raise KeycloakStartError(f"Failed to start Keycloak: {e}")

    def _is_port_in_use(self, port: int) -> bool:
        """
        Check if a port is currently in use.

        Args:
            port: Port number to check

        Returns:
            True if port is in use, False otherwise
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Set SO_REUSEADDR to allow binding even if port is in TIME_WAIT
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("localhost", port))
                return False
            except OSError:
                return True

    def _find_available_ports(
        self, start_port: int = 8080, max_attempts: int = 100
    ) -> tuple[int, int]:
        """
        Find a pair of available ports (HTTP and management).

        Searches for a port P where both P and P+1000 are available.

        Args:
            start_port: Port to start searching from
            max_attempts: Maximum number of ports to try

        Returns:
            Tuple of (http_port, management_port)

        Raises:
            KeycloakStartError: If no available port pair found
        """
        for port_offset in range(max_attempts):
            http_port = start_port + port_offset
            mgmt_port = http_port + 1000

            # Check if both ports are available
            if not self._is_port_in_use(http_port) and not self._is_port_in_use(mgmt_port):
                logger.debug(
                    f"Found available ports: {http_port} (HTTP) and {mgmt_port} (management)"
                )
                return (http_port, mgmt_port)

        raise KeycloakStartError(
            f"Could not find available port pair after {max_attempts} attempts starting from {start_port}"
        )

    def stop(self, timeout: int = 10) -> None:
        """
        Stop the Keycloak server gracefully.

        Steps:
        1. Send SIGTERM to the process
        2. Wait up to timeout seconds
        3. If still running, send SIGKILL

        Args:
            timeout: Max seconds to wait for graceful shutdown
        """
        with self._lock:
            if not self.is_running():
                logger.debug("Keycloak is not running, nothing to stop")
                return

            if self.process is None:
                return

            logger.info(f"🛑 Stopping Keycloak server (port {self.port})...")

            try:
                # Send SIGTERM
                self.process.terminate()

                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=timeout)
                    logger.info("✅ Keycloak stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill
                    logger.warning("⚠️  Keycloak did not stop gracefully, forcing kill")
                    self.process.kill()
                    self.process.wait()
                    logger.info("✅ Keycloak process killed")

            except Exception as e:
                logger.error(f"Error stopping Keycloak: {e}")
            finally:
                self.process = None

                # Wait for output thread to finish
                if self._output_thread and self._output_thread.is_alive():
                    self._output_thread.join(timeout=2)
                self._output_thread = None

                # Clean up realm config file if it exists
                if self.realm_config_file and self.realm_config_file.exists():
                    try:
                        self.realm_config_file.unlink()
                        logger.debug(f"Cleaned up realm config file: {self.realm_config_file}")
                        self.realm_config_file = None
                    except Exception as e:
                        logger.warning(f"Failed to clean up realm config file: {e}")

                # Restore data and conf directories to original state
                self._restore_directories()

    def is_running(self) -> bool:
        """
        Check if Keycloak process is running.

        Returns:
            True if the process is running
        """
        if self.process is None:
            return False

        # Check if process is still alive
        return self.process.poll() is None

    def wait_for_ready(self, timeout: int = 60, realm_name: Optional[str] = None) -> None:
        """
        Poll the health endpoint until ready.

        Poll: GET http://localhost:{management_port}/health/ready
        Should return 200 when ready.

        Note: In Keycloak 26.x, health endpoints are exposed on the management
        port, which is configurable via --http-management-port.

        Args:
            timeout: Max seconds to wait
            realm_name: Optional realm name to verify after health check passes

        Raises:
            KeycloakTimeoutError: If not ready within timeout
        """
        # Health endpoint is on the configured management port
        url = f"http://localhost:{self.management_port}/health/ready"
        start_time = time.time()
        interval = 2

        logger.info(f"Waiting for Keycloak to be ready at {url}...")

        # First wait for health endpoint
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info("Keycloak is ready")
                    break
            except requests.RequestException:
                # Connection errors are expected during startup; ignore and retry
                pass

            # Check if process is still running
            if not self.is_running():
                raise KeycloakTimeoutError(
                    f"Keycloak process terminated. Check logs at {self.log_file}"
                )

            time.sleep(interval)
        else:
            raise KeycloakTimeoutError(
                f"Keycloak did not become ready within {timeout} seconds. Check logs at {self.log_file}"
            )

        # If a realm was imported, verify it's accessible
        if realm_name:
            logger.info(f"Verifying realm '{realm_name}' is accessible...")
            realm_url = f"{self.get_base_url()}/realms/{realm_name}"

            while time.time() - start_time < timeout:
                try:
                    response = requests.get(realm_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Realm '{realm_name}' is accessible")
                        return
                except requests.RequestException:
                    pass

                # Check if process is still running
                if not self.is_running():
                    raise KeycloakTimeoutError(
                        f"Keycloak process terminated. Check logs at {self.log_file}"
                    )

                time.sleep(interval)

            raise KeycloakTimeoutError(
                f"Realm '{realm_name}' did not become accessible within {timeout} seconds. Check logs at {self.log_file}"
            )

    def get_base_url(self) -> str:
        """
        Return base URL.

        Returns:
            Base URL (http://localhost:{port})
        """
        return f"http://localhost:{self.port}"

    def cleanup(self) -> None:
        """
        Clean up resources.

        - Stop server if running
        - Optionally delete installation (not implemented by default for safety)
        """
        self.stop()

        # Note: We don't delete the installation by default to allow reuse
        # across test sessions. Users can manually delete ~/.keycloak-test
        # if they want to clean up.
        logger.info(f"Keycloak installation preserved at {self.install_dir}")
