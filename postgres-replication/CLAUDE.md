# AI Agent Instructions — postgres-replication

This file captures all instructions given to the AI agent that built and
maintains this project.

---

## Project goal

A Python CLI tool that installs and manages **one or more independent
PostgreSQL instances** on a single Ubuntu machine.  The canonical demo uses
two instances to prove they are completely independent.

---

## Technology constraints

| Requirement | Choice |
|-------------|--------|
| Language | Python ≥ 3.11 |
| CLI framework | [Click](https://click.palletsprojects.com/) |
| Dependency manager | [uv](https://docs.astral.sh/uv/) |
| DB adapter | [psycopg v3](https://www.psycopg.org/) (`psycopg[binary]`) |
| Config format | TOML (`tomllib` stdlib) |
| Type checker | [ty](https://github.com/astral-sh/ty) (`uv tool install ty`) |
| Test framework | pytest (integration tests against real postgres, **no mocking**) |

---

## CLI commands

Entry point: `postgres-manager` (defined in `pyproject.toml [project.scripts]`).

| Command | Purpose | Needs root |
|---------|---------|-----------|
| `install` | Add PGDG apt repo, install `postgresql-<version>`, init cluster | Yes |
| `start` | Start cluster, create/update admin user | Yes |
| `stop` | Stop cluster gracefully | No |
| `create-table` | Create database + demo table in one instance | No |
| `insert` | Insert a row into one instance | No |
| `query` | Query rows from one instance | No |

All commands accept:
- `--config PATH` — override default `config.toml`
- `--instance NAME` — select instance by `cluster_name` or 1-based index
- `--instance` is **optional** when only one `[[instances]]` block is configured

---

## Configuration file (`config.toml`)

Location: project root (`postgres-replication/config.toml`).

Uses a TOML array of tables (`[[instances]]`) — add as many blocks as needed.
No `data_dir` field (Ubuntu `pg_createcluster` manages the path).

**Passwords are never stored in the config file.**  They are accepted via:
- `--password` CLI flag
- `PGPASSWORD` environment variable
- CLI flag takes precedence over env var

---

## Project layout

```
postgres-replication/
├── config.toml                     # Non-sensitive runtime configuration
├── pyproject.toml                  # uv / build metadata
├── uv.lock                         # Locked dependencies
├── README.md                       # Usage and developer guide
├── CLAUDE.md                       # This file (AI agent instructions)
├── src/
│   └── postgres_manager/
│       ├── __init__.py
│       ├── cli.py                  # Click commands
│       ├── config.py               # Config loading + resolve_instance()
│       └── postgres.py             # All PostgreSQL operations
└── tests/
    ├── conftest.py                 # Session fixture: real PG clusters on 25432/25433
    ├── test_config.py              # Unit tests for config parsing (no DB)
    ├── test_postgres.py            # Integration tests for postgres.py functions
    └── test_cli.py                 # Integration tests for CLI commands
```

---

## PostgreSQL instance management (Ubuntu)

Uses `pg_createcluster` / `pg_ctlcluster` from the `postgresql-common` package:

```
pg_createcluster 18 main1 --port=5432 -- --auth-local=trust --auth-host=scram-sha-256
pg_ctlcluster 18 main1 start
pg_ctlcluster 18 main1 stop -- -m fast
```

After starting, the tool connects via the unix socket (trust auth) as `postgres`
and issues `CREATE ROLE pgadmin1 WITH LOGIN SUPERUSER PASSWORD '...'` using
`psycopg.sql.Literal` for the password (DDL does not accept `$N` parameters).

---

## Key design decisions

- **Single-instance commands**: each CLI command targets exactly one instance
  (selected by `--instance`).  Call the command twice to operate on two instances.
- **N-instance config**: `[[instances]]` is a TOML array — supports 1 to N instances.
  Auto-selection when N=1; required `--instance` when N>1.
- **SQL safety**: dynamic SQL uses `psycopg.sql.SQL` + `psycopg.sql.Identifier`.
  Parameter values use `%s`.  DDL passwords use `psycopg.sql.Literal`.
- **Idempotency**: `install` skips existing clusters; `create-table` uses
  `CREATE TABLE IF NOT EXISTS`; `create_database` checks before creating.
- **No passwords in config**: resolved at runtime from CLI args or `PGPASSWORD`.

---

## Integration tests

Tests use **real PostgreSQL** clusters — no mocking.

The `pg_instances` session fixture (in `conftest.py`):
1. Creates two clusters: `pytest1` (port 25432) and `pytest2` (port 25433)
   using `pg_createcluster` against the installed PG version (currently 16).
2. Starts them and creates admin users `testadmin1` / `testadmin2`.
3. Tears everything down after the session.

Each test calls commands for **both** instances and verifies the data differs.
The key tests are `test_two_instances_hold_different_data` (postgres layer) and
`test_instances_contain_different_data` / `test_two_instances_have_different_rows`
(CLI layer).

---

## Running checks

```bash
# Type check
uv run ty check src/ tests/

# Tests (requires postgres to be installed, root access needed for setup)
uv run pytest -v

# Install the CLI tool
uv run postgres-manager --help
```
