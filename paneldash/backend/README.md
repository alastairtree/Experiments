# PanelDash Backend

FastAPI backend for the PanelDash multi-tenant operations dashboard.

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run linting
uv run ruff check .
uv run mypy .
```

## Testing

### Test Modes

The test suite automatically adapts based on PostgreSQL availability:

**Without Database:**
- API tests run (using in-memory test client)
- Migration structure tests run (syntax validation)
- Database schema tests skip gracefully

**With Database Running:**
- All tests run
- Migrations are automatically applied to the test database
- Full schema validation (tables, columns, constraints, indexes)

### Running Tests with Database

```bash
# Start PostgreSQL
docker-compose up postgres-central -d

# Run all tests (migrations run automatically)
uv run pytest

# Run only database tests
uv run pytest tests/integration/test_database.py -v
```

The `test_db_setup` fixture automatically:
1. Checks if PostgreSQL is available
2. Runs `alembic upgrade head` if available
3. Provides migrations for all tests
4. Tests skip gracefully if database unavailable

## Database Setup

### Prerequisites

You need a running PostgreSQL instance. The easiest way is to use Docker:

```bash
# Start PostgreSQL (from project root)
cd ../..
docker-compose up postgres-central postgres-tenant -d
```

### Running Migrations

```bash
# Create a new migration (after modifying models)
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history

# View current migration
uv run alembic current
```

### Seeding Development Data

After running migrations, seed the database with test data:

```bash
# Seed the database
uv run python scripts/seed_db.py
```

This creates:
- 3 test users (admin, user1, user2)
- 2 test tenants (tenant-alpha, tenant-beta)
- User-tenant access mappings

See the main README.md in the project root for more information.
