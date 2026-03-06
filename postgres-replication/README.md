# postgres-replication

A Python CLI tool that installs and manages **two independent PostgreSQL 18
instances** on a single machine. Each instance runs on a different port, has a
dedicated admin user, and holds its own copy of a demo database — providing a
clear demonstration that they are entirely separate.

---

## Contents

- [Requirements](#requirements)
- [Installation (tool)](#installation-tool)
- [Configuration](#configuration)
- [Password handling](#password-handling)
- [CLI commands](#cli-commands)
- [End-to-end walkthrough](#end-to-end-walkthrough)
- [Running the tests](#running-the-tests)
- [Type checking](#type-checking)

---

## Requirements

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| [uv](https://docs.astral.sh/uv/) | any recent |
| Ubuntu / Debian | 22.04 LTS "Jammy" or later (for `pg_createcluster`) |
| Root / sudo access | required for `install` and `start` commands |

> **Note:** The `install` command downloads PostgreSQL 18 from the official
> [PGDG apt repository](https://www.postgresql.org/download/linux/ubuntu/).
> An internet connection is required the first time you run it.

---

## Installation (tool)

```bash
# Clone the repository (if you haven't already)
git clone <repo-url>
cd postgres-replication

# Create the virtual environment and install all dependencies
uv sync

# Install the CLI in editable mode
uv pip install -e .
```

After this, the `postgres-manager` command is available inside the `uv` environment:

```bash
uv run postgres-manager --help
```

---

## Configuration

All non-sensitive settings live in `config.toml` at the root of this directory:

```toml
[postgres]
version = 18

[instance1]
cluster_name = "main1"
port         = 5432
admin_user   = "pgadmin1"
data_dir     = "/var/lib/postgresql/18/main1"
socket_dir   = "/var/run/postgresql"

[instance2]
cluster_name = "main2"
port         = 5433
admin_user   = "pgadmin2"
data_dir     = "/var/lib/postgresql/18/main2"
socket_dir   = "/var/run/postgresql"

[database]
name = "demodb"

[table]
name = "demo"
```

You can supply a custom config file with `--config <path>` on any command.

---

## Password handling

**Passwords are never stored in the config file.** Supply them either as
environment variables or as CLI flags:

| Instance | Environment variable | CLI flag |
|----------|---------------------|----------|
| Instance 1 | `PGPASSWORD1` | `--password1 <pw>` |
| Instance 2 | `PGPASSWORD2` | `--password2 <pw>` |

CLI flags take precedence over environment variables.

Recommended approach (set once in your shell session):

```bash
export PGPASSWORD1="super_secret_1"
export PGPASSWORD2="super_secret_2"
```

---

## CLI commands

All commands accept `--config <path>` to override the default config file.

### `install`

> Requires root / sudo

Adds the PGDG apt repository, installs the `postgresql-18` package, and
initialises two separate clusters.

```bash
sudo uv run postgres-manager install
```

### `start`

> Requires root / sudo

Starts both clusters and creates (or updates) the admin users with the
provided passwords.

```bash
sudo -E uv run postgres-manager start \
    --password1 "$PGPASSWORD1" \
    --password2 "$PGPASSWORD2"
```

(`-E` preserves environment variables so `PGPASSWORD*` env vars work with sudo.)

### `stop`

Stops both clusters gracefully.

```bash
sudo uv run postgres-manager stop
```

### `create-table`

Creates the demo database (same name in each instance) and the `demo` table.
Run this after `start`.

```bash
uv run postgres-manager create-table \
    --password1 "$PGPASSWORD1" \
    --password2 "$PGPASSWORD2"
```

### `insert`

Inserts a unique row into each instance's `demo` table so the two instances
hold different data.

```bash
uv run postgres-manager insert \
    --password1 "$PGPASSWORD1" \
    --password2 "$PGPASSWORD2"
```

### `query`

Queries the `demo` table from both instances and prints a side-by-side
comparison. Outputs a confirmation that the instances are independent.

```bash
uv run postgres-manager query \
    --password1 "$PGPASSWORD1" \
    --password2 "$PGPASSWORD2"
```

---

## End-to-end walkthrough

```bash
# 1. Set passwords
export PGPASSWORD1="admin1_password"
export PGPASSWORD2="admin2_password"

# 2. Install PostgreSQL 18 and create both clusters (needs root)
sudo uv run postgres-manager install

# 3. Start both clusters and create admin users (needs root)
sudo -E uv run postgres-manager start

# 4. Create databases and tables
uv run postgres-manager create-table

# 5. Insert distinct rows into each instance
uv run postgres-manager insert

# 6. Query both instances to confirm they are independent
uv run postgres-manager query
```

Expected output from `query`:

```
Querying 'demo' in 'demodb' from both instances...

--- Instance 1 (main1, port 5432) ---
  id=1  instance='main1'  message='Hello from instance 1 (main1)'  created=...

--- Instance 2 (main2, port 5433) ---
  id=1  instance='main2'  message='Hello from instance 2 (main2)'  created=...

✓ Instances hold different data — confirmed independent instances.
```

---

## Running the tests

Tests use **pytest** with mocks — no live PostgreSQL installation is required.

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_config.py -v
```

### Test coverage

| File | What is tested |
|------|----------------|
| `tests/test_config.py` | Config loading, error handling, connection string builder |
| `tests/test_postgres.py` | All postgres operations (mocked subprocess + psycopg) |
| `tests/test_cli.py` | All Click commands via `CliRunner` |

---

## Type checking

The project uses [**ty**](https://github.com/astral-sh/ty) for static type
analysis.

```bash
# Check source files
uv run ty check src/

# Check both source and tests
uv run ty check src/ tests/
```

ty is installed automatically as part of `uv sync` (it is listed as a global
tool; install it once with `uv tool install ty` if needed).
