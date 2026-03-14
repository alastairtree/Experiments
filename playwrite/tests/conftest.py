"""Pytest configuration and fixtures for Playwright tests."""

import socket
import threading
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import BrowserType

# Paths
ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config.toml"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"


def load_config() -> dict:
    """Load browser configuration from config.toml."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {"browser": {"headless": True, "browser_type": "chromium"}}


def find_free_port() -> int:
    """Find an available local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(url: str, timeout: float = 15.0) -> None:
    """Poll until the server responds or timeout is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise TimeoutError(f"Server at {url} did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """Override Playwright launch args with settings from config.toml."""
    config = load_config()
    headless = config.get("browser", {}).get("headless", True)
    return {**browser_type_launch_args, "headless": headless}


@pytest.fixture(scope="session")
def browser_type(playwright, browser_type_launch_args) -> BrowserType:  # type: ignore[override]
    """Select browser type from config.toml (default: chromium)."""
    config = load_config()
    browser_name = config.get("browser", {}).get("browser_type", "chromium")
    return getattr(playwright, browser_name)


@pytest.fixture(scope="session")
def live_server() -> Generator[str, None, None]:
    """Start the Flask development server in a background thread."""
    from hello_world.server import app

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    wait_for_server(base_url)
    yield base_url


@pytest.fixture(autouse=True)
def ensure_screenshots_dir() -> None:
    """Ensure screenshots directory exists before every test."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
