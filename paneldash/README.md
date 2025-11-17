# PanelDash - Multi-Tenant Operations Dashboard

A self-hosted, multi-tenant operations dashboard and reporting system providing real-time health monitoring, status tracking, and data visualization.

## Features

- **Multi-Tenancy**: Isolated databases and configurations per tenant
- **Flexible Panels**: Time series, KPI metrics, health status, tables, and custom panels
- **YAML Configuration**: Easy-to-manage dashboard and panel definitions
- **Real-Time Monitoring**: Auto-refreshing panels with configurable intervals
- **Interactive Visualizations**: Built with Plotly.js for rich data exploration
- **Authentication**: Integrated with Keycloak for secure access control
- **Data Aggregation**: Intelligent time-bucketing for large datasets

## Technology Stack

### Backend
- FastAPI (async Python web framework)
- SQLAlchemy 2.0 with asyncpg
- PostgreSQL (multi-database architecture)
- Keycloak authentication
- uv package management

### Frontend
- React with TypeScript
- Vite build tool
- Plotly.js for visualizations
- TanStack Table and Query
- Tailwind CSS

## Project Structure

```
paneldash/
├── backend/              # FastAPI backend application
│   ├── app/             # Application code
│   │   ├── api/         # API endpoints
│   │   ├── auth/        # Authentication logic
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   └── custom_panels/ # Custom panel implementations
│   ├── tests/           # Backend tests
│   ├── alembic/         # Database migrations
│   └── pyproject.toml   # Python dependencies
├── frontend/            # React frontend application
│   ├── src/            # Source code
│   │   ├── components/ # React components
│   │   ├── pages/      # Page components
│   │   ├── api/        # API client
│   │   ├── types/      # TypeScript types
│   │   └── utils/      # Utility functions
│   └── package.json    # Node dependencies
├── config/             # Tenant configurations (YAML)
├── docker/             # Docker configurations
└── tests/              # End-to-end tests
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker and Docker Compose (for full stack)
- uv (Python package manager)

### Backend Setup

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Running with Docker

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (central + tenant databases)
- Keycloak
- Backend API
- Frontend

## Development

### Backend Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Linting
uv run ruff check .
uv run mypy .

# Database migrations
uv run alembic upgrade head
```

### Frontend Commands

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm run test

# Run E2E tests
npm run test:e2e

# Linting
npm run lint

# Type checking
npm run type-check

# Build for production
npm run build
```

## Configuration

Dashboards and panels are configured using YAML files in the `config/tenants/` directory.

Example dashboard configuration:

```yaml
dashboard:
  name: "System Health Dashboard"
  refresh_interval: 21600
  layout:
    columns: 12
  panels:
    - id: "cpu_usage"
      config_file: "panels/cpu_usage.yaml"
      position:
        row: 1
        col: 1
        width: 8
        height: 2
```

See `dashboard-specification.md` for complete configuration reference.

## Testing

- **Unit Tests**: `uv run pytest` (backend) / `npm run test` (frontend)
- **Integration Tests**: `uv run pytest tests/integration`
- **E2E Tests**: `npm run test:e2e`

## Documentation

- [Dashboard Specification](./dashboard-specification.md) - Complete technical specification
- API Documentation - Available at `/docs` when running the backend
- Configuration Guide - See specification document

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Status

🚧 **In Development** - Currently implementing Phase 1 (Foundation & Authentication)

See `dashboard-specification.md` for the complete implementation roadmap.
