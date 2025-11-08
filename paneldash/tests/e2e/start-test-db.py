#!/usr/bin/env python3
"""Start a PostgreSQL test database using pgserver."""

import sys
import time
from pathlib import Path
from tempfile import mkdtemp
from pgserver import get_server


def main():
    """Start PostgreSQL server and print connection info."""
    # Create a temporary directory for the PostgreSQL data
    pgdata = Path(mkdtemp(prefix="paneldash-e2e-db-"))

    # Get a PostgreSQL server instance
    server = get_server(pgdata, cleanup_mode="delete")

    # Start the server
    server.ensure_pgdata_inited()
    server.ensure_postgres_running()

    # Get connection info
    info = server.get_postmaster_info()

    # Print connection details to stdout (will be parsed by Node.js)
    print(f"PGHOST={info.socket_dir or 'localhost'}")
    print(f"PGPORT={info.port}")
    print(f"PGDATABASE=postgres")
    print(f"PGUSER=postgres")
    print(f"READY=true")
    sys.stdout.flush()

    # Keep the server running until interrupted
    try:
        print("PostgreSQL server running. Press Ctrl+C to stop.", file=sys.stderr)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PostgreSQL server...", file=sys.stderr)
        server.cleanup()


if __name__ == "__main__":
    main()
