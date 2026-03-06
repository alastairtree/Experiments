# postgres-replication

A Python CLI tool that installs and manages **one or more independent PostgreSQL
instances** on a single machine.  Each command targets a single instance,
selected by name or index.  The demo workflow uses two instances to prove they
are completely independent.

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

All non-sensitive settings live in `config.toml` at the root of this directory.
Define as many `[[instances]]` blocks as you need:

```toml
[postgres]
version = 18

[[instances]]
cluster_name = "main1"
port         = 5432
admin_user   = "pgadmin1"
socket_dir   = "/var/run/postgresql"   # optional, default shown

[[instances]]
cluster_name = "main2"
port         = 5433
admin_user   = "pgadmin2"

[database]
name = "demodb"

[table]
name = "demo"
```

You can supply a custom config file with `--config <path>` on any command.

### Selecting an instance

All commands accept `--instance NAME` (or `-i NAME`) to choose which instance
to operate on.

| Scenario | Behaviour |
|----------|-----------|
| Single `[[instances]]` in config | `--instance` is **optional** — the only instance is used automatically |
| Multiple `[[instances]]` in config | `--instance` is **required** |

`NAME` can be either the `cluster_name` value or a 1-based position (e.g. `1`, `2`).

---

## Password handling

**Passwords are never stored in the config file.**  Supply them either as
environment variables or as CLI flags:

| Source | Variable / flag |
|--------|----------------|
| Environment variable | `PGPASSWORD` |
| CLI flag | `--password <pw>` |

CLI flags take precedence over environment variables.

Recommended approach (set once in your shell session):

```bash
export PGPASSWORD="super_secret"
```

---

## CLI commands

All commands accept `--config <path>` and `--instance NAME`.

### `install`

> Requires root / sudo

Adds the PGDG apt repository, installs the `postgresql-<version>` package,
and initialises a cluster for the selected instance.

```bash
sudo uv run postgres-manager install --instance main1
sudo uv run postgres-manager install --instance main2
```

### `start`

> Requires root / sudo

Starts a cluster and creates (or updates) the admin user with the given password.

```bash
sudo -E uv run postgres-manager start --instance main1
sudo -E uv run postgres-manager start --instance main2
```

(`-E` preserves `PGPASSWORD` so the env var works with sudo.)

### `stop`

Stops a cluster gracefully.

```bash
sudo uv run postgres-manager stop --instance main1
```

### `create-table`

Creates the database and the `demo` table in one instance.

```bash
uv run postgres-manager create-table --instance main1
uv run postgres-manager create-table --instance main2
```

### `insert`

Inserts a row into one instance's `demo` table.

```bash
uv run postgres-manager insert --instance main1 --message "Hello from instance 1"
uv run postgres-manager insert --instance main2 --message "Hello from instance 2"
```

### `query`

Queries the `demo` table from one instance.

```bash
uv run postgres-manager query --instance main1
uv run postgres-manager query --instance main2
```

---

## End-to-end walkthrough

```bash
# 1. Set the password (same or different for each instance)
export PGPASSWORD="admin_password"

# 2. Install PostgreSQL 18 and create both clusters (needs root)
sudo uv run postgres-manager install --instance main1
sudo uv run postgres-manager install --instance main2

# 3. Start both clusters and create admin users (needs root)
sudo -E uv run postgres-manager start --instance main1
sudo -E uv run postgres-manager start --instance main2

# 4. Create databases and tables
uv run postgres-manager create-table --instance main1
uv run postgres-manager create-table --instance main2

# 5. Insert a different row into each instance
uv run postgres-manager insert --instance main1 --message "Hello from instance 1"
uv run postgres-manager insert --instance main2 --message "Hello from instance 2"

# 6. Query each instance to confirm they are independent
uv run postgres-manager query --instance main1
uv run postgres-manager query --instance main2
```

Expected output from `query --instance main1`:

```
--- main1 (port 5432) ---
  id=1  instance='main1'  message='Hello from instance 1'  created=...
```

Expected output from `query --instance main2`:

```
--- main2 (port 5433) ---
  id=1  instance='main2'  message='Hello from instance 2'  created=...
```

---

## Running the tests

Integration tests use **real PostgreSQL clusters** — no mocking.  The
session-scoped fixture in `conftest.py` creates two temporary clusters on ports
**25432** and **25433** using the installed PostgreSQL version, runs all tests,
then drops the clusters.

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific file
uv run pytest tests/test_cli.py -v
```

### Test structure

| File | What is tested |
|------|----------------|
| `tests/test_config.py` | Config loading, `resolve_instance`, connection string builder — no DB needed |
| `tests/test_postgres.py` | `create_database`, `create_table`, `insert_row`, `query_rows` against real PG |
| `tests/test_cli.py` | All Click commands via `CliRunner` against real PG |

Key integration assertions:
- Each command is called **twice** (once per instance).
- `test_two_instances_hold_different_data` / `test_instances_contain_different_data`
  verify that the two instances are truly independent.

---

## Type checking

The project uses [**ty**](https://github.com/astral-sh/ty) for static type analysis.

```bash
# Install ty (once)
uv tool install ty

# Check source files
uv run ty check src/

# Check source and tests
uv run ty check src/ tests/
```
