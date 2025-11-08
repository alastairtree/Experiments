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

# Run linting
uv run ruff check .
uv run mypy .
```

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
