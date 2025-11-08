# PanelDash - Claude Development Guide

This guide helps you understand the PanelDash project and how to work on it effectively.

## Project Overview

PanelDash is a **multi-tenant operations dashboard** providing real-time health monitoring, status tracking, and data visualization. It's a self-hosted solution with YAML-based configuration.

**Tech Stack:**
- **Backend:** FastAPI + SQLAlchemy 2.0 + PostgreSQL + Keycloak + Python 3.11+
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + Plotly.js
- **Infrastructure:** Docker Compose, GitHub Actions CI/CD

## Architecture

### Multi-Tenancy Model
- **Central Database:** Stores users, tenants, and mappings
- **Tenant Databases:** One PostgreSQL database per tenant with operational data
- **Configuration:** Each tenant has YAML configs in `config/tenants/{tenant-id}/`

### Key Directories

```
paneldash/
├── .claude/                    # This directory - development guides
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # Application entry point
│   │   ├── config.py          # Settings (Pydantic)
│   │   ├── database.py        # Multi-tenant DB manager
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── api/v1/            # API endpoints
│   │   ├── services/          # Business logic
│   │   └── auth/              # Keycloak integration
│   ├── tests/                 # Backend tests
│   ├── alembic/               # Database migrations
│   └── pyproject.toml         # Dependencies (uv)
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── main.tsx           # App entry
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── api/               # API client
│   │   └── types/             # TypeScript types
│   ├── tests/                 # Frontend tests
│   └── package.json           # Dependencies (npm)
├── docker/                     # Dockerfiles
├── config/                     # Tenant configurations (YAML)
├── tests/                      # E2E tests (Playwright)
├── docker-compose.yml          # Development stack
├── docker-compose.prod.yml     # Production stack
└── dashboard-specification.md  # Complete technical spec
```

## Quick Start

### First Time Setup

```bash
# Backend
cd paneldash/backend
uv sync --all-extras

# Frontend
cd paneldash/frontend
npm install

# Playwright (for E2E tests)
cd paneldash
npx playwright install
```

### Development Workflow

**Backend:**
```bash
cd paneldash/backend
uv run uvicorn app.main:app --reload    # Dev server on :8000
uv run pytest                           # Run tests
uv run ruff check . && uv run mypy .    # Lint & type check
```

**Frontend:**
```bash
cd paneldash/frontend
npm run dev              # Dev server on :3000
npm run test             # Run tests
npm run lint             # Lint
npm run type-check       # TypeScript check
```

**E2E Tests:**
```bash
cd paneldash
npm run test:e2e         # Run Playwright E2E tests
```

**Docker (Full Stack):**
```bash
cd paneldash
docker-compose up -d                    # Start all services
docker-compose logs -f backend          # View logs
docker-compose down                     # Stop services
```

## Development Guidelines

### Code Quality Standards

1. **Type Safety:**
   - Backend: 100% type hints (mypy strict mode)
   - Frontend: Strict TypeScript mode enabled
   - No `any` types without justification

2. **Linting:**
   - Backend: `ruff check .` must pass
   - Frontend: `npm run lint` must pass
   - Format: ruff handles backend, prettier/eslint for frontend

3. **Testing:**
   - Unit tests: >70% coverage target
   - Integration tests: All API endpoints
   - E2E tests: Critical user flows
   - All tests must pass before commit

### Git Workflow

**Current Branch:** `claude/paneldash-review-011CUuuA2heJnVQSiy8CnQGs`

**Commit Format:**
```
Step X: Brief description

Detailed explanation of changes:
- What was added/changed
- Why it was necessary
- Any acceptance criteria met

All acceptance criteria met:
✅ Criterion 1
✅ Criterion 2
```

**Before Committing:**
```bash
# Backend
cd backend && uv run ruff check . && uv run mypy . && uv run pytest

# Frontend
cd frontend && npm run lint && npm run type-check && npm run test

# E2E
cd .. && npm run test:e2e
```

## Project Status

### Current Phase: Phase 1 - Foundation & Authentication

**Completed Steps:**
- ✅ Step 1: Project initialization (uv, npm, configs)
- ✅ Step 2: Docker infrastructure (compose, Dockerfiles)
- ✅ Step 3: Backend project structure (SQLAlchemy, Alembic)

**Next Steps (Steps 4-10):**
- Step 4: Central database models (users, tenants, mappings)
- Step 5: Keycloak integration
- Step 6: User & tenant management API
- Step 7: Frontend project setup
- Step 8: Authentication UI
- Step 9: Tenant selection UI
- Step 10: Admin user management UI

**Total Progress:** 47 steps planned, 3 completed (6%)

### Implementation Reference

See `dashboard-specification.md` for:
- Complete 47-step roadmap
- Panel types and configuration
- API endpoint specifications
- Database schemas
- Testing requirements
- Performance targets

## Common Tasks

### Adding a Database Model

1. Create model in `backend/app/models/`
2. Import in `backend/alembic/env.py`
3. Generate migration: `uv run alembic revision --autogenerate -m "description"`
4. Review migration in `backend/alembic/versions/`
5. Apply: `uv run alembic upgrade head`

### Adding an API Endpoint

1. Define Pydantic schemas in `backend/app/schemas/`
2. Create endpoint in `backend/app/api/v1/`
3. Register router in `backend/app/main.py`
4. Add integration test in `backend/tests/integration/`
5. Update OpenAPI docs

### Adding a React Component

1. Create component in `frontend/src/components/`
2. Define TypeScript types in `frontend/src/types/`
3. Add unit test in `frontend/src/tests/components/`
4. Import and use in page component

### Running Specific Tests

```bash
# Backend - specific test
cd backend && uv run pytest tests/unit/test_config_loader.py -v

# Frontend - specific test
cd frontend && npm run test -- src/components/Header.test.tsx

# E2E - specific test
cd paneldash && npx playwright test tests/e2e/health.spec.ts
```

## Debugging

### Backend Debugging
- Check logs: Server prints to stdout
- Enable debug mode: Set `DEBUG=true` in `.env`
- Database queries: SQLAlchemy echo enabled in debug mode
- Use FastAPI `/docs` for interactive API testing

### Frontend Debugging
- React DevTools browser extension
- Check browser console for errors
- Network tab for API calls
- Vite dev server shows build errors

### Database Issues
```bash
# Connect to central database
docker-compose exec postgres-central psql -U postgres -d paneldash_central

# Connect to tenant database
docker-compose exec postgres-tenant psql -U postgres -d tenant_alpha

# View migrations
cd backend && uv run alembic current
cd backend && uv run alembic history
```

## Useful URLs (when running)

- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Frontend:** http://localhost:3000
- **Keycloak Admin:** http://localhost:8080 (admin/admin)

## Performance Targets

- API Response: <500ms (p95)
- Dashboard Load: <2s initial render
- Panel Refresh: <1s per panel
- Support: 50+ concurrent users per tenant
- Data: Handle 10M+ rows per tenant database

## Security Checklist

- ✅ All API endpoints require authentication (except /health)
- ✅ SQL injection prevention (parameterized queries only)
- ✅ Tenant isolation (database-level separation)
- ✅ Input validation (Pydantic schemas)
- ⏳ CSRF protection (to be implemented)
- ⏳ Rate limiting (to be implemented)

## Getting Help

1. **Specification:** Read `dashboard-specification.md` for detailed requirements
2. **Code:** Check existing implementations as reference
3. **Errors:** Search error messages in codebase first
4. **Architecture:** Review this guide and project structure

## Quick Reference

### Environment Variables

Key variables in `.env`:
- `CENTRAL_DB_HOST`, `CENTRAL_DB_PORT`, `CENTRAL_DB_NAME`: Central database
- `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`: Keycloak config
- `DEBUG`: Enable debug mode

### Dependencies

**Backend (uv):**
- Add: `uv add package-name`
- Add dev: `uv add --dev package-name`
- Sync: `uv sync`

**Frontend (npm):**
- Add: `npm install package-name`
- Add dev: `npm install -D package-name`

---

**Ready to build!** Start with the specification, understand the architecture, and maintain code quality. 🚀
