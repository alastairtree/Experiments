# AI Agent Instructions — postgres-replication

This file captures the full set of instructions given to the AI agent that
built this project. Refer to it when continuing or extending the work.

---

## Project goal

Write a Python CLI tool that:

1. **Installs two instances of PostgreSQL 18** on the local (Ubuntu) machine.
2. **Starts both instances** with two different database admin users.
3. **Connects to each instance** separately and creates a database of the same
   name in each, plus a table named `demo`.
4. **Inserts a different row** into each instance.
5. **Queries both instances** to demonstrate they are independent.

---

## Technology constraints

| Requirement | Choice |
|-------------|--------|
| Language | Python ≥ 3.11 |
| CLI framework | [Click](https://click.palletsprojects.com/) |
| Dependency manager | [uv](https://docs.astral.sh/uv/) |
| DB adapter | [psycopg v3](https://www.psycopg.org/) (`psycopg[binary]`) |
| Config format | TOML (`tomllib` stdlib + `tomli-w` for writing) |
| Type checker | [ty](https://github.com/astral-sh/ty) (`uv tool install ty`) |
| Test framework | pytest + pytest-mock |

---

## CLI commands

The entry point is `postgres-manager` (installed via `pyproject.toml`
`[project.scripts]`).

| Command | Purpose | Needs root |
|---------|---------|-----------|
| `install` | Add PGDG apt repo, install `postgresql-18`, init two clusters | Yes |
| `start` | Start both clusters, create/update admin users | Yes |
| `stop` | Stop both clusters gracefully | Yes |
| `create-table` | Create database + demo table in both instances | No |
| `insert` | Insert a unique row into each instance | No |
| `query` | Query and display rows from both instances | No |

---

## Configuration file (`config.toml`)

Location: project root (`postgres-replication/config.toml`).

Stores: PostgreSQL version, two instance configs (cluster name, port, admin
username, data dir, socket dir), database name, table name.

**Passwords are never stored in the config file.** They are accepted via:
- CLI flags: `--password1` / `--password2`
- Environment variables: `PGPASSWORD1` / `PGPASSWORD2`
- CLI flags take precedence over env vars.

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
│       ├── config.py               # Config loading (TOML → dataclasses)
│       └── postgres.py             # All PostgreSQL operations
└── tests/
    ├── conftest.py                 # Shared fixtures
    ├── test_config.py              # Config module tests
    ├── test_postgres.py            # Postgres operations tests (mocked)
    └── test_cli.py                 # CLI command tests (Click CliRunner)
```

---

## PostgreSQL instance management (Ubuntu)

The tool uses the Debian/Ubuntu `pg_createcluster` / `pg_ctlcluster` utilities:

- **`pg_createcluster 18 main1 --port=5432 -- --auth-local=trust --auth-host=scram-sha-256`**
  Creates cluster with trust auth on the local unix socket (so the `start`
  command can bootstrap admin users without needing an initial password).
- **`pg_ctlcluster 18 main1 start`** — starts the cluster.
- **`pg_ctlcluster 18 main1 stop -- -m fast`** — stops it.

After starting, the tool connects via the unix socket (trust auth) as the
default `postgres` superuser and issues:
```sql
CREATE ROLE pgadmin1 WITH LOGIN SUPERUSER PASSWORD %s;
```
(or `ALTER ROLE` if it already exists).

Subsequent operations use TCP connections on the configured port with the new
admin credentials.

---

## Key design decisions

- **SQL injection safety**: All dynamic SQL (table names, role names) uses
  `psycopg.sql.SQL` + `psycopg.sql.Identifier`. Parameter values use `%s`
  placeholders. No f-strings are used in SQL queries.
- **Idempotency**: `install` skips clusters that already exist; `create-table`
  uses `CREATE TABLE IF NOT EXISTS`; `create_database` checks before creating.
- **Error handling**: Each CLI command catches `FileNotFoundError`,
  `KeyError`, and `PostgresError` and exits with a non-zero code.
- **No passwords in config**: Passwords are resolved at runtime from CLI args
  or env vars; `_get_passwords()` in `cli.py` enforces this.

---

## Running checks

```bash
# Type check
uv run ty check src/

# Tests (no live DB required — all mocked)
uv run pytest -v

# Install tool
uv run postgres-manager --help
```

---

## Extending the project

- To add a new cluster, duplicate an `[instanceN]` block in `config.toml` and
  update `AppConfig` + `cli.py` to reference it.
- To support replication between instances, add a `replication` section to
  `config.toml` and implement `setup_replication()` in `postgres.py`.
- Passwords could be stored in a system keyring (e.g. `keyring` library)
  instead of env vars for better UX without sacrificing security.
