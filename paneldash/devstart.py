#!/usr/bin/env python3
"""Developer setup script for PanelDash.

This script orchestrates the complete development environment:
1. Installs and starts a Keycloak server with configured realm and users
2. Starts a local PostgreSQL database using pgserver
3. Starts the backend API with proper configuration
4. Starts the frontend with proper configuration
5. Monitors all processes and provides health checks

Usage:
    pip install httpx
    sudo apt-get update && sudo apt-get install -y openjdk-17-jdk
    cd ../keycloak && ./build.sh --skip-tests        
    cd ../paneldash/
    sudo apt-get install -y postgresql-client
    python devstart.py [--clean] [--no-frontend]

Options:
    --clean         Clean up all previous data and start fresh
    --no-frontend   Skip starting the frontend (useful for API-only development)
"""

import argparse
import atexit
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Project paths
SCRIPT_DIR = Path(__file__).parent.absolute()
BACKEND_DIR = SCRIPT_DIR / "backend"
FRONTEND_DIR = SCRIPT_DIR / "frontend"
KEYCLOAK_DIR = SCRIPT_DIR.parent / "keycloak"
KEYCLOAK_WHEEL = KEYCLOAK_DIR / "dist" / "pytest_keycloak_fixture-0.1.0-py3-none-any.whl"

# Process tracking
processes = []


def cleanup_processes():
    """Clean up all spawned processes on exit."""
    logger.info("🧹 Cleaning up processes...")
    for proc, name in processes:
        if proc.poll() is None:
            logger.info(f"  Stopping {name}...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"  Force killing {name}...")
                proc.kill()
                proc.wait()
    logger.info("✅ Cleanup complete")


atexit.register(cleanup_processes)


def handle_signal(signum, frame):
    """Handle interrupt signals gracefully."""
    logger.info(f"\n🛑 Received signal {signum}, shutting down...")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def check_dependencies():
    """Check that all required dependencies are available."""
    logger.info("🔍 Checking dependencies...")

    # Check Python version
    if sys.version_info < (3, 11):
        logger.error("❌ Python 3.11 or higher is required")
        sys.exit(1)

    # Check Java (for Keycloak)
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=10
        )
        logger.info("✅ Java is available")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("❌ Java is not installed. Please install Java 17 or higher")
        sys.exit(1)

    # Check Node.js (for frontend)
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        logger.info(f"✅ Node.js is available: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("❌ Node.js is not installed")
        sys.exit(1)

    # Check npm (for frontend)
    try:
        result = subprocess.run(
            ["npm", "--version"], capture_output=True, text=True, timeout=10
        )
        logger.info(f"✅ npm is available: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("❌ npm is not installed")
        sys.exit(1)

    # Check if keycloak wheel exists
    if not KEYCLOAK_WHEEL.exists():
        logger.error(f"❌ Keycloak wheel not found at {KEYCLOAK_WHEEL}")
        logger.error("   Please run: cd ../keycloak && ./build.sh --skip-tests")
        sys.exit(1)

    logger.info("✅ All dependencies are available")


def install_keycloak_library():
    """Install the pytest-keycloak-fixture library."""
    logger.info("📦 Installing Keycloak library...")

    # Install the wheel
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", str(KEYCLOAK_WHEEL)],
            check=True,
            capture_output=True,
        )
        logger.info("✅ Keycloak library installed")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install Keycloak library: {e}")
        logger.error(f"   stdout: {e.stdout.decode()}")
        logger.error(f"   stderr: {e.stderr.decode()}")
        sys.exit(1)


def start_keycloak(port: int = 8080):
    """Start Keycloak server with configured realm and users."""
    logger.info("🔑 Starting Keycloak server...")

    # Import after installation
    from pytest_keycloak.config import ClientConfig, RealmConfig, UserConfig
    from pytest_keycloak.manager import KeycloakManager

    # Configure realm with users and clients
    realm_config = RealmConfig(
        realm="paneldash",
        enabled=True,
        users=[
            UserConfig(
                username="testuser",
                password="testpass",
                email="testuser@example.com",
                first_name="Test",
                last_name="User",
                enabled=True,
                realm_roles=["user"],
            ),
            UserConfig(
                username="adminuser",
                password="adminpass",
                email="admin@example.com",
                first_name="Admin",
                last_name="User",
                enabled=True,
                realm_roles=["user", "admin"],
            ),
        ],
        clients=[
            # Frontend client (public)
            ClientConfig(
                client_id="paneldash-frontend",
                enabled=True,
                public_client=True,
                redirect_uris=[
                    "http://localhost:5173/*",
                    "http://localhost:5174/*",
                    "http://localhost:3000/*",
                ],
                web_origins=[
                    "+",  # Allow all origins from redirect_uris
                ],
                direct_access_grants_enabled=True,
                standard_flow_enabled=True,  # Enable authorization code flow
                implicit_flow_enabled=False,
                full_scope_allowed=True,
            ),
            # Backend API client (confidential)
            ClientConfig(
                client_id="paneldash-api",
                enabled=True,
                public_client=False,
                secret="your-api-client-secret",
                redirect_uris=["http://localhost:8000/*", "http://localhost:8001/*"],
                web_origins=["http://localhost:8000", "http://localhost:8001"],
                direct_access_grants_enabled=True,
            ),
        ],
    )

    # Create Keycloak manager
    manager = KeycloakManager(
        version="26.0.7",
        port=port,
        admin_user="admin",
        admin_password="admin",
        management_port=port + 1000,
    )

    # Check Java version
    manager.check_java_version()

    # Download and install if needed
    if not manager.keycloak_dir.exists():
        logger.info("📥 Downloading Keycloak (this may take a few minutes)...")
        manager.download_and_install()

    # Start the server
    manager.start(realm_config=realm_config.to_keycloak_json(), wait_for_ready=True, timeout=120)

    logger.info(f"✅ Keycloak is running on http://localhost:{port}")
    logger.info(f"   Admin console: http://localhost:{port}/admin")
    logger.info(f"   Realm: paneldash")
    logger.info(f"   Test user: testuser / testpass")
    logger.info(f"   Admin user: adminuser / adminpass")

    return manager


def start_postgres():
    """Start PostgreSQL server using pgserver."""
    logger.info("🐘 Starting PostgreSQL server...")

    # Check if pgserver is installed
    try:
        import pgserver
    except ImportError:
        logger.info("   Installing pgserver...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pgserver>=0.1.4"],
            check=True,
            capture_output=True,
        )
        import pgserver

    # Create a temporary directory for the PostgreSQL data
    pgdata = Path(mkdtemp(prefix="paneldash-dev-db-"))
    logger.info(f"   PostgreSQL data directory: {pgdata}")

    # Get a PostgreSQL server instance
    server = pgserver.get_server(pgdata, cleanup_mode="delete")

    # Start the server
    server.ensure_pgdata_inited()
    server.ensure_postgres_running()

    # Get connection info
    info = server.get_postmaster_info()

    logger.info(f"✅ PostgreSQL is running")
    logger.info(f"   Socket: {info.socket_dir or 'localhost'}")
    logger.info(f"   Port: {info.port}")

    return server, info


def create_database(db_info):
    """Create the paneldash_central database."""
    logger.info("📊 Creating database...")

    # Use psql to create the database
    env = os.environ.copy()
    env["PGHOST"] = db_info.socket_dir or "localhost"
    env["PGPORT"] = str(db_info.port)
    env["PGUSER"] = "postgres"

    try:
        subprocess.run(
            ["psql", "-c", "CREATE DATABASE paneldash_central;"],
            env=env,
            check=True,
            capture_output=True,
        )
        logger.info("✅ Database created")
    except subprocess.CalledProcessError as e:
        # Database might already exist, which is okay
        if b"already exists" in e.stderr:
            logger.info("✅ Database already exists")
        else:
            logger.error(f"❌ Failed to create database: {e.stderr.decode()}")
            raise


def run_migrations(db_info):
    """Run database migrations."""
    logger.info("🔄 Running database migrations...")

    # Set up environment for alembic
    env = os.environ.copy()
    if db_info.socket_dir:
        env["CENTRAL_DB_HOST"] = db_info.socket_dir
    else:
        env["CENTRAL_DB_HOST"] = "localhost"
    env["CENTRAL_DB_PORT"] = str(db_info.port)
    env["CENTRAL_DB_NAME"] = "paneldash_central"
    env["CENTRAL_DB_USER"] = "postgres"
    env["CENTRAL_DB_PASSWORD"] = ""

    try:
        # Run alembic upgrade
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("✅ Migrations complete")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Migrations failed: {e}")
        logger.error(f"   stdout: {e.stdout}")
        logger.error(f"   stderr: {e.stderr}")
        # Don't fail - migrations might already be applied
        logger.warning("   Continuing anyway...")


def start_backend(db_info, keycloak_port: int = 8080):
    """Start the backend API server."""
    logger.info("🚀 Starting backend API...")

    # Set up environment
    env = os.environ.copy()
    if db_info.socket_dir:
        env["CENTRAL_DB_HOST"] = db_info.socket_dir
    else:
        env["CENTRAL_DB_HOST"] = "localhost"
    env["CENTRAL_DB_PORT"] = str(db_info.port)
    env["CENTRAL_DB_NAME"] = "paneldash_central"
    env["CENTRAL_DB_USER"] = "postgres"
    env["CENTRAL_DB_PASSWORD"] = ""
    env["KEYCLOAK_SERVER_URL"] = f"http://localhost:{keycloak_port}"
    env["KEYCLOAK_REALM"] = "paneldash"
    env["KEYCLOAK_CLIENT_ID"] = "paneldash-api"
    env["KEYCLOAK_CLIENT_SECRET"] = "your-api-client-secret"
    env["DEBUG"] = "true"

    # Start uvicorn
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    processes.append((proc, "Backend API"))

    # Wait for backend to be ready
    logger.info("   Waiting for backend to be ready...")
    for i in range(30):
        try:
            response = httpx.get("http://localhost:8001/health", timeout=2)
            if response.status_code == 200:
                logger.info("✅ Backend is running on http://localhost:8001")
                logger.info("   API docs: http://localhost:8001/docs")
                return proc
        except Exception:
            pass
        time.sleep(1)

    logger.error("❌ Backend failed to start within 30 seconds")
    # Print some output for debugging
    if proc.poll() is not None:
        logger.error("   Backend process has exited!")
    sys.exit(1)


def start_frontend(keycloak_port: int = 8080):
    """Start the frontend development server."""
    logger.info("🎨 Starting frontend...")

    # Set up environment
    env = os.environ.copy()
    env["VITE_API_URL"] = "http://localhost:8001"
    env["VITE_KEYCLOAK_URL"] = f"http://localhost:{keycloak_port}"
    env["VITE_KEYCLOAK_REALM"] = "paneldash"
    env["VITE_KEYCLOAK_CLIENT_ID"] = "paneldash-frontend"

    # Check if node_modules exists, if not run npm install
    if not (FRONTEND_DIR / "node_modules").exists():
        logger.info("   Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True, env=env)

    # Start vite dev server
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "5173", "--host", "0.0.0.0"],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    processes.append((proc, "Frontend"))

    # Wait a bit for frontend to start
    logger.info("   Waiting for frontend to be ready...")
    time.sleep(5)

    if proc.poll() is not None:
        logger.error("❌ Frontend process has exited!")
        sys.exit(1)

    logger.info("✅ Frontend is running on http://localhost:5173")
    return proc


def monitor_processes():
    """Monitor all processes and restart if they crash."""
    logger.info("\n" + "=" * 60)
    logger.info("🎉 Development environment is ready!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Services:")
    logger.info("  🔑 Keycloak:    http://localhost:8080")
    logger.info("  🔑 Admin Console: http://localhost:8080/admin (admin/admin)")
    logger.info("  🚀 Backend API: http://localhost:8001")
    logger.info("  📖 API Docs:    http://localhost:8001/docs")
    logger.info("  🎨 Frontend:    http://localhost:5173")
    logger.info("")
    logger.info("Test Credentials:")
    logger.info("  👤 Regular User: testuser / testpass")
    logger.info("  👤 Admin User:   adminuser / adminpass")
    logger.info("")
    logger.info("Press Ctrl+C to stop all services")
    logger.info("=" * 60)
    logger.info("")

    try:
        while True:
            time.sleep(2)
            # Check if any process has died
            for proc, name in processes:
                if proc.poll() is not None:
                    logger.error(f"❌ {name} has stopped unexpectedly!")
                    sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Start PanelDash development environment")
    parser.add_argument("--clean", action="store_true", help="Clean up all previous data")
    parser.add_argument(
        "--no-frontend", action="store_true", help="Skip starting the frontend"
    )
    parser.add_argument("--keycloak-port", type=int, default=8080, help="Keycloak port")
    args = parser.parse_args()

    logger.info("🚀 Starting PanelDash Development Environment")
    logger.info("=" * 60)

    # Check dependencies
    check_dependencies()

    # Install Keycloak library
    install_keycloak_library()

    # Start Keycloak
    keycloak_manager = start_keycloak(port=args.keycloak_port)

    # Start PostgreSQL
    pg_server, pg_info = start_postgres()

    # Create database
    create_database(pg_info)

    # Run migrations
    run_migrations(pg_info)

    # Start backend
    backend_proc = start_backend(pg_info, keycloak_port=args.keycloak_port)

    # Start frontend (unless disabled)
    if not args.no_frontend:
        frontend_proc = start_frontend(keycloak_port=args.keycloak_port)

    # Monitor processes
    monitor_processes()


if __name__ == "__main__":
    main()
