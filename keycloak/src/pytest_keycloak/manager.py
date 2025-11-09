"""Keycloak lifecycle management."""

import atexit
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from threading import Lock
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

    def __init__(
        self,
        version: str = "26.0.7",
        install_dir: Optional[Path] = None,
        port: Optional[int] = None,
        admin_user: str = "admin",
        admin_password: str = "admin",
        management_port: Optional[int] = None,
    ):
        """
        Initialize KeycloakManager.

        Args:
            version: Keycloak version to download
            install_dir: Where to install Keycloak (default: ~/.keycloak-test)
            port: HTTP port for Keycloak (default: auto-select from 8080+)
            admin_user: Admin username
            admin_password: Admin password
            management_port: Management/health port (default: port + 1000)
        """
        self.version = version
        self.install_dir = install_dir or Path.home() / ".keycloak-test"
        self._explicit_port = port is not None or management_port is not None
        self.port = port if port is not None else 8080
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.management_port = management_port if management_port is not None else self.port + 1000

        self.keycloak_dir = self.install_dir / f"keycloak-{version}"
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.log_file: Optional[Path] = None

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler for atexit."""
        if self.is_running():
            try:
                self.stop()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

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

            # Check if requested ports are available, find alternatives if needed
            if self._explicit_port:
                # User specified ports - try them first, but find alternatives if busy
                if self._is_port_in_use(self.port) or self._is_port_in_use(self.management_port):
                    logger.info(f"⚠️  Requested ports {self.port}/{self.management_port} in use, finding alternatives...")
                    http_port, mgmt_port = self._find_available_ports(start_port=self.port)
                    logger.info(f"🔍 Selected available ports: {http_port} (HTTP), {mgmt_port} (management)")
                    self.port = http_port
                    self.management_port = mgmt_port
            else:
                # Auto-select ports starting from default
                http_port, mgmt_port = self._find_available_ports(start_port=self.port)
                if http_port != self.port or mgmt_port != self.management_port:
                    logger.info(f"🔍 Auto-selected available ports: {http_port} (HTTP), {mgmt_port} (management)")
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

                realm_name = realm_config.get("realm", "unknown")
                logger.info(f"📝 Configuring Keycloak with realm: {realm_name}")
                logger.info(f"   Realm configuration written to {realm_file}")

            # Prepare log file
            log_dir = self.install_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            self.log_file = log_dir / f"keycloak-{self.port}.log"

            # Prepare environment
            env = os.environ.copy()
            env["KEYCLOAK_ADMIN"] = self.admin_user
            env["KEYCLOAK_ADMIN_PASSWORD"] = self.admin_password

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

            try:
                # Start process
                with open(self.log_file, "w") as log_f:
                    self.process = subprocess.Popen(
                        cmd,
                        cwd=self.keycloak_dir,
                        env=env,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                    )

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
                    self.wait_for_ready(timeout=timeout)
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

    def _wait_for_ports_release(self, timeout: int = 10) -> None:
        """
        Wait for HTTP and management ports to be released.

        Args:
            timeout: Max seconds to wait for ports to be released
        """
        start_time = time.time()
        ports_to_check = [self.port, self.management_port]

        while time.time() - start_time < timeout:
            if not any(self._is_port_in_use(p) for p in ports_to_check):
                logger.debug(f"Ports {ports_to_check} released")
                return
            time.sleep(0.2)

        logger.warning(f"Ports {ports_to_check} still in use after {timeout}s")

    def _find_available_ports(self, start_port: int = 8080, max_attempts: int = 100) -> tuple[int, int]:
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
                logger.debug(f"Found available ports: {http_port} (HTTP) and {mgmt_port} (management)")
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
        4. Wait for ports to be released

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
                # Wait for ports to be released before returning
                self._wait_for_ports_release(timeout=5)

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

    def wait_for_ready(self, timeout: int = 60) -> None:
        """
        Poll the health endpoint until ready.

        Poll: GET http://localhost:{management_port}/health/ready
        Should return 200 when ready.

        Note: In Keycloak 26.x, health endpoints are exposed on the management
        port, which is configurable via --http-management-port.

        Args:
            timeout: Max seconds to wait

        Raises:
            KeycloakTimeoutError: If not ready within timeout
        """
        # Health endpoint is on the configured management port
        url = f"http://localhost:{self.management_port}/health/ready"
        start_time = time.time()
        interval = 2

        logger.info(f"Waiting for Keycloak to be ready at {url}...")

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info("Keycloak is ready")
                    return
            except requests.RequestException:
                # Connection errors are expected during startup; ignore and retry
                pass

            # Check if process is still running
            if not self.is_running():
                raise KeycloakTimeoutError(
                    f"Keycloak process terminated. Check logs at {self.log_file}"
                )

            time.sleep(interval)

        raise KeycloakTimeoutError(
            f"Keycloak did not become ready within {timeout} seconds. Check logs at {self.log_file}"
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
