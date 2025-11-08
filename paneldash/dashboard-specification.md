# Multi-Tenant Operations Dashboard - Software Development Specification

## Overview

A self-hosted, multi-tenant operations dashboard and reporting system providing real-time health monitoring, status tracking, and data visualization. The system supports multiple tenants with isolated databases, configurable panels defined in YAML, and interactive data exploration capabilities.

## Technology Stack

### Backend
- **Framework**: FastAPI (async Python web framework)
- **Database ORM**: SQLAlchemy 2.0 with asyncpg driver
- **Database**: PostgreSQL (one database per tenant + one central database)
- **Authentication**: Keycloak (self-hosted, Docker-based)
- **Configuration**: Pydantic Settings
- **Migrations**: Alembic
- **Package Management**: uv
- **Linting**: ruff + mypy
- **Testing**: pytest + pytest-asyncio + httpx

### Frontend
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **Visualization**: Plotly.js (via react-plotly.js)
- **Data Tables**: TanStack Table
- **API Client**: TanStack Query (React Query)
- **Date Handling**: date-fns
- **Styling**: Tailwind CSS
- **Testing**: Vitest + React Testing Library + Playwright (E2E)

### Infrastructure
- **Deployment**: Docker Compose
- **CI/CD**: GitHub Actions
- **In-Memory Caching**: Python dictionaries/LRU cache (no Redis)

## Core Concepts

### Multi-Tenancy Model
- **Central Database**: Stores user accounts, tenant metadata, user-tenant mappings
- **Tenant Databases**: One PostgreSQL database per tenant containing operational data
- **Configuration**: Each tenant has a dedicated folder in the repository with YAML configuration files

### Panel Types
1. **Time Series Line Plots**: Interactive line charts with date-based data
2. **KPI Metrics**: Single metric displays with threshold-based coloring
3. **Health Status Panels**: Red/Amber/Green status indicators
4. **Sortable Tables**: Tabular data with sorting, filtering, and pagination
5. **Custom Image Panels**: Server-rendered images
6. **Custom Template Panels**: Server-side JSON rendered via inline templates

### Dashboard Structure
- Each tenant has one **default dashboard** (mandatory)
- Additional **named dashboards** (optional)
- **Reports**: Single-panel or table-only views for focused data analysis

## Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Pydantic settings
│   │   ├── database.py             # Database connection management
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── keycloak.py         # Keycloak integration
│   │   │   └── dependencies.py     # Auth dependencies
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── central.py          # Central DB models
│   │   │   └── base.py             # SQLAlchemy base
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User schemas
│   │   │   ├── tenant.py           # Tenant schemas
│   │   │   ├── dashboard.py        # Dashboard schemas
│   │   │   └── panel.py            # Panel data schemas
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py         # Authentication endpoints
│   │   │   │   ├── tenants.py      # Tenant selection
│   │   │   │   ├── dashboards.py   # Dashboard endpoints
│   │   │   │   ├── panels.py       # Panel data endpoints
│   │   │   │   └── users.py        # User management (admin)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── config_loader.py    # YAML config parser
│   │   │   ├── panel_factory.py    # Panel type handlers
│   │   │   ├── data_aggregator.py  # Time-bucket aggregation
│   │   │   ├── query_builder.py    # SQL query generation
│   │   │   └── cache.py            # In-memory caching
│   │   └── custom_panels/
│   │       ├── __init__.py
│   │       └── registry.py         # Custom panel registration
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py             # Pytest fixtures
│   │   ├── unit/
│   │   │   ├── test_config_loader.py
│   │   │   ├── test_data_aggregator.py
│   │   │   └── test_query_builder.py
│   │   └── integration/
│   │       ├── test_api.py
│   │       └── test_database.py
│   ├── alembic/                    # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── pyproject.toml              # uv project config
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # Root component
│   │   ├── api/
│   │   │   ├── client.ts           # API client setup
│   │   │   └── queries.ts          # TanStack Query hooks
│   │   ├── components/
│   │   │   ├── panels/
│   │   │   │   ├── TimeSeriesPanel.tsx
│   │   │   │   ├── KPIPanel.tsx
│   │   │   │   ├── HealthStatusPanel.tsx
│   │   │   │   ├── TablePanel.tsx
│   │   │   │   ├── CustomImagePanel.tsx
│   │   │   │   └── CustomTemplatePanel.tsx
│   │   │   ├── layout/
│   │   │   │   ├── DashboardGrid.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── TenantSelector.tsx
│   │   │   └── common/
│   │   │       ├── DateFilter.tsx
│   │   │       └── DrillDownModal.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Report.tsx
│   │   │   └── Admin.tsx
│   │   ├── types/
│   │   │   ├── dashboard.ts
│   │   │   ├── panel.ts
│   │   │   └── api.ts
│   │   ├── utils/
│   │   │   └── dateHelpers.ts
│   │   └── tests/
│   │       ├── components/
│   │       └── integration/
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── config/
│   ├── tenants/
│   │   ├── tenant-alpha/
│   │   │   ├── dashboards/
│   │   │   │   ├── default.yaml
│   │   │   │   └── performance.yaml
│   │   │   └── panels/
│   │   │       ├── cpu_usage.yaml
│   │   │       ├── error_rate.yaml
│   │   │       └── health_status.yaml
│   │   └── tenant-beta/
│   │       ├── dashboards/
│   │       │   └── default.yaml
│   │       └── panels/
│   │           └── system_uptime.yaml
│   └── schema.yaml                 # Config validation schema
├── tests/
│   └── e2e/
│       ├── dashboard.spec.ts
│       ├── auth.spec.ts
│       └── panel-interactions.spec.ts
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
└── README.md
```

## Configuration Schema

### Dashboard Configuration (`dashboards/default.yaml`)

```yaml
dashboard:
  name: "System Health Dashboard"
  description: "Main operational dashboard"
  refresh_interval: 21600  # seconds (6 hours)
  
  layout:
    columns: 12  # Grid system (like Bootstrap)
    
  panels:
    - id: "cpu_usage"
      config_file: "panels/cpu_usage.yaml"
      position:
        row: 1
        col: 1
        width: 8  # columns
        height: 2  # rows
        
    - id: "memory_kpi"
      config_file: "panels/memory_kpi.yaml"
      position:
        row: 1
        col: 9
        width: 4
        height: 1
        
    - id: "system_health"
      config_file: "panels/health_status.yaml"
      position:
        row: 2
        col: 9
        width: 4
        height: 1
```

### Panel Configurations

#### Time Series Panel (`panels/cpu_usage.yaml`)

```yaml
panel:
  type: "timeseries"
  title: "CPU Usage Over Time"
  description: "Server CPU utilization percentage"
  
  data_source:
    table: "metrics"
    columns:
      timestamp: "recorded_at"
      value: "cpu_percent"
      series_label: "server_name"  # Optional: multiple lines
    
  query:
    where: "metric_type = 'cpu'"
    order_by: "recorded_at DESC"
    
  display:
    y_axis_label: "CPU %"
    y_axis_range: [0, 100]
    line_color: "#3B82F6"
    fill_area: true
    
  refresh_interval: 300  # 5 minutes
  
  drill_down:
    enabled: true
    show_table: true
    disable_aggregation: true
```

#### KPI Panel (`panels/memory_kpi.yaml`)

```yaml
panel:
  type: "kpi"
  title: "Current Memory Usage"
  
  data_source:
    table: "metrics"
    columns:
      value: "memory_percent"
    query: "metric_type = 'memory' ORDER BY recorded_at DESC LIMIT 1"
    
  display:
    unit: "%"
    decimals: 1
    thresholds:
      - value: 0
        color: "#10B981"    # Green
        label: "good"
      - value: 70
        color: "#F59E0B"    # Amber
        label: "warning"
      - value: 90
        color: "#EF4444"    # Red
        label: "critical"
        
  refresh_interval: 60
```

#### Health Status Panel (`panels/health_status.yaml`)

```yaml
panel:
  type: "health_status"
  title: "Service Health"
  
  data_source:
    table: "service_health"
    columns:
      service_name: "name"
      status_value: "last_check_status"
      timestamp: "last_checked_at"
      
  display:
    status_mapping:
      0: 
        color: "#10B981"  # Green
        label: "Healthy"
      1:
        color: "#F59E0B"  # Amber
        label: "Degraded"
      2:
        color: "#EF4444"  # Red
        label: "Down"
        
  refresh_interval: 120
```

#### Table Panel (`panels/error_log.yaml`)

```yaml
panel:
  type: "table"
  title: "Recent Errors"
  
  data_source:
    table: "error_logs"
    columns:
      - name: "timestamp"
        display: "Time"
        format: "datetime"
      - name: "service"
        display: "Service"
      - name: "error_message"
        display: "Error"
      - name: "severity"
        display: "Severity"
        
    query:
      where: "severity IN ('ERROR', 'CRITICAL')"
      order_by: "timestamp DESC"
      limit: 50
      
  display:
    sortable: true
    default_sort: "timestamp"
    default_sort_order: "desc"
    pagination: 25
    
  refresh_interval: 300
```

#### Custom Image Panel (`panels/custom_chart.yaml`)

```yaml
panel:
  type: "custom_image"
  title: "Network Topology"
  
  endpoint: "/api/v1/custom/network-topology"
  
  parameters:
    include_offline: false
    
  refresh_interval: 3600
```

#### Custom Template Panel (`panels/custom_summary.yaml`)

```yaml
panel:
  type: "custom_template"
  title: "Daily Summary"
  
  endpoint: "/api/v1/custom/daily-summary"
  
  template: |
    <div class="p-4">
      <h3 class="text-lg font-bold">Summary for {{ date }}</h3>
      <ul class="mt-2">
        <li>Total Requests: {{ total_requests }}</li>
        <li>Error Rate: {{ error_rate }}%</li>
        <li>Avg Response Time: {{ avg_response_time }}ms</li>
      </ul>
    </div>
    
  refresh_interval: 21600
```

## Default Panel Sizing

```python
DEFAULT_PANEL_SIZES = {
    "timeseries": {"width": 8, "height": 2},
    "kpi": {"width": 4, "height": 1},
    "health_status": {"width": 4, "height": 1},
    "table": {"width": 12, "height": 3},
    "custom_image": {"width": 6, "height": 2},
    "custom_template": {"width": 6, "height": 2},
}
```

## Data Aggregation Rules

Time-based aggregation for time series data:

| Time Range | Bucket Size | Strategy |
|------------|-------------|----------|
| ≤ 8 hours | None | Return all data points |
| ≤ 1 day | 1 minute | Average per minute |
| ≤ 4 days | 10 minutes | Average per 10 minutes |
| > 4 days | 1 hour | Average per hour |

Implementation in SQL (PostgreSQL):

```sql
-- Example for 10-minute buckets
SELECT 
    date_trunc('minute', timestamp) - 
    (EXTRACT(minute FROM timestamp)::int % 10) * interval '1 minute' as bucket,
    AVG(value) as value,
    series_label
FROM metrics
WHERE timestamp BETWEEN :start_date AND :end_date
GROUP BY bucket, series_label
ORDER BY bucket
```

## API Endpoints

### Authentication & Authorization

```
POST   /api/v1/auth/login              # Keycloak OAuth flow
POST   /api/v1/auth/logout             # Invalidate session
GET    /api/v1/auth/me                 # Current user info
```

### Tenant Management

```
GET    /api/v1/tenants                 # List user's accessible tenants
POST   /api/v1/tenants/:id/select      # Set active tenant for session
```

### Dashboard

```
GET    /api/v1/dashboards              # List dashboards for active tenant
GET    /api/v1/dashboards/:name        # Get dashboard config
```

### Panel Data

```
GET    /api/v1/panels/:id/data         # Get panel data
  Query params:
    - start_date: ISO 8601 datetime
    - end_date: ISO 8601 datetime
    - disable_aggregation: boolean (default: false)
    - series_filter: optional filter for multi-series
```

### Reports

```
GET    /api/v1/reports/:panel_id       # Single panel report view
GET    /api/v1/reports/:panel_id/export # Export as CSV/JSON
```

### Admin (Admin users only)

```
GET    /api/v1/admin/users             # List all users
POST   /api/v1/admin/users             # Create user
PUT    /api/v1/admin/users/:id         # Update user
DELETE /api/v1/admin/users/:id         # Delete user
POST   /api/v1/admin/users/:id/tenants # Assign tenant access
```

### Custom Panels

```
GET    /api/v1/custom/:endpoint        # Custom panel data endpoint
```

## Database Schema

### Central Database

```sql
-- Users table (synced from Keycloak or managed internally)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keycloak_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(100) UNIQUE NOT NULL,  -- e.g., 'tenant-alpha'
    name VARCHAR(255) NOT NULL,
    database_name VARCHAR(255) NOT NULL,
    database_host VARCHAR(255) NOT NULL,
    database_port INTEGER DEFAULT 5432,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-Tenant mapping
CREATE TABLE user_tenants (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, tenant_id)
);

CREATE INDEX idx_user_tenants_user ON user_tenants(user_id);
CREATE INDEX idx_user_tenants_tenant ON user_tenants(tenant_id);
```

### Tenant Databases

Schema is tenant-specific and defined by their operational needs. No required schema, but examples:

```sql
-- Example metrics table
CREATE TABLE metrics (
    id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMP NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    server_name VARCHAR(255),
    cpu_percent DECIMAL(5,2),
    memory_percent DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_recorded_at ON metrics(recorded_at);
CREATE INDEX idx_metrics_type ON metrics(metric_type);

-- Example service health table
CREATE TABLE service_health (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    last_check_status INTEGER NOT NULL,  -- 0=healthy, 1=degraded, 2=down
    last_checked_at TIMESTAMP NOT NULL,
    error_message TEXT
);
```

## Development Steps

### Phase 1: Foundation & Authentication (Steps 1-10)

#### Step 1: Project Initialization
- Initialize Git repository
- Set up `pyproject.toml` with uv for backend dependencies
- Set up `package.json` for frontend dependencies
- Configure ruff and mypy in `pyproject.toml`
- Create basic `.gitignore`, `README.md`

**Acceptance Criteria:**
- `uv sync` successfully installs backend dependencies
- `npm install` successfully installs frontend dependencies
- `ruff check .` and `mypy .` run without errors

#### Step 2: Docker Infrastructure Setup
- Create `docker-compose.yml` with services:
  - PostgreSQL (central database)
  - PostgreSQL (tenant database template)
  - Keycloak
  - Backend (FastAPI)
  - Frontend (Vite dev server / nginx for prod)
- Create Dockerfiles for backend and frontend
- Set up volume mounts for development

**Acceptance Criteria:**
- `docker-compose up` starts all services
- Keycloak admin console accessible
- Databases accept connections

#### Step 3: Backend Project Structure
- Create FastAPI application skeleton in `backend/app/main.py`
- Set up Pydantic Settings in `config.py`
- Configure SQLAlchemy with asyncpg
- Create database connection manager with multi-database support
- Set up Alembic for migrations

**Acceptance Criteria:**
- FastAPI app starts and serves docs at `/docs`
- Database connections succeed
- Health check endpoint returns 200

#### Step 4: Central Database Models & Migrations
- Define SQLAlchemy models for `users`, `tenants`, `user_tenants`
- Create initial Alembic migration
- Write database seed script for development data

**Acceptance Criteria:**
- `alembic upgrade head` creates all tables
- Seed script populates test users and tenants
- SQLAlchemy queries work in Python REPL

#### Step 5: Keycloak Integration
- Configure Keycloak realm and client
- Implement Keycloak token validation in `backend/app/auth/keycloak.py`
- Create FastAPI dependency for authentication
- Create authentication endpoints (login callback, logout, me)

**Acceptance Criteria:**
- Users can authenticate via Keycloak
- JWT tokens are validated correctly
- `/api/v1/auth/me` returns user information

#### Step 6: User & Tenant Management API
- Implement tenant listing endpoint
- Implement tenant selection (store in session/JWT)
- Implement user management endpoints (admin only)
- Add user-tenant assignment endpoints

**Acceptance Criteria:**
- Users can list their accessible tenants
- Tenant selection persists for subsequent requests
- Admin users can manage user-tenant mappings

#### Step 7: Frontend Project Setup
- Initialize Vite + React + TypeScript project
- Configure Tailwind CSS
- Set up TanStack Query for API calls
- Create API client with authentication headers
- Implement basic routing (React Router)

**Acceptance Criteria:**
- Vite dev server runs
- Tailwind classes work
- API client successfully calls backend

#### Step 8: Authentication UI
- Create login page with Keycloak integration
- Implement logout functionality
- Create authenticated route wrapper
- Display user information in header

**Acceptance Criteria:**
- Users can log in via Keycloak
- Protected routes redirect to login
- Logout clears session

#### Step 9: Tenant Selection UI
- Create tenant selector dropdown component
- Store selected tenant in React state
- Pass tenant context to all API calls

**Acceptance Criteria:**
- Dropdown shows user's tenants
- Selection persists during session
- Tenant change triggers data refresh

#### Step 10: Admin User Management UI
- Create admin page (accessible to admin users only)
- List all users
- Assign/remove tenant access
- Basic user CRUD operations

**Acceptance Criteria:**
- Admin users see admin page
- Non-admin users get 403 error
- User-tenant assignments can be modified

---

### Phase 2: Configuration System & Panel Framework (Steps 11-20)

#### Step 11: YAML Configuration Loader
- Implement `config_loader.py` service
- Define Pydantic models for validating YAML configs
- Load dashboard and panel configs from filesystem
- Cache parsed configs in memory

**Acceptance Criteria:**
- YAML files are parsed correctly
- Invalid configs raise validation errors
- Config changes reload without restart (dev mode)

#### Step 12: Panel Factory & Registry
- Create `panel_factory.py` with panel type registry
- Implement base panel class
- Register built-in panel types
- Create factory method to instantiate panels from config

**Acceptance Criteria:**
- Panel factory creates panel instances from YAML
- Unknown panel types raise clear errors
- Panel instances validate their specific config

#### Step 13: SQL Query Builder
- Implement `query_builder.py` service
- Generate SELECT queries from panel configs
- Add WHERE clause injection with parameterization
- Support date range filtering
- Validate table/column names against SQL injection

**Acceptance Criteria:**
- Generated queries are valid PostgreSQL
- Date filters apply correctly
- SQL injection attempts are blocked

#### Step 14: Data Aggregation Engine
- Implement `data_aggregator.py` with time-bucket logic
- Support minute, 10-minute, hour buckets
- Implement averaging and interpolation
- Add disable_aggregation flag support

**Acceptance Criteria:**
- Data aggregates correctly by time bucket
- Aggregation rules apply based on date range
- Drill-down can disable aggregation

#### Step 15: Dashboard API Endpoints
- Implement `/api/v1/dashboards` endpoint
- Load dashboard config for active tenant
- Return dashboard metadata and panel list
- Include panel sizing and positioning

**Acceptance Criteria:**
- API returns dashboard config as JSON
- Tenant-specific configs are loaded
- Non-existent dashboards return 404

#### Step 16: Panel Data API - Time Series
- Implement `/api/v1/panels/:id/data` for time series
- Query tenant database
- Apply date filtering
- Apply aggregation
- Return JSON with timestamps and values

**Acceptance Criteria:**
- Time series data returns correctly
- Aggregation applies based on date range
- Multiple series (grouped by label) work

#### Step 17: Panel Data API - KPI & Health Status
- Extend panel data endpoint for KPI panels
- Add support for health status panels
- Apply threshold logic in response
- Return current status with color codes

**Acceptance Criteria:**
- KPI panels return single value with threshold status
- Health panels return status for multiple services
- Threshold colors match config

#### Step 18: Panel Data API - Tables
- Extend panel data endpoint for table panels
- Support sorting parameters
- Support pagination
- Return tabular data with metadata

**Acceptance Criteria:**
- Table data returns with correct columns
- Sorting works on any column
- Pagination returns correct page

#### Step 19: Dashboard Grid Layout Component
- Create `DashboardGrid.tsx` with CSS Grid
- Support 12-column layout system
- Position panels based on config
- Make responsive for mobile (stack panels)

**Acceptance Criteria:**
- Panels render in correct grid positions
- Layout is responsive on mobile
- Grid handles different panel sizes

#### Step 20: Date Filter Component
- Create global date filter UI
- Support common presets (Last 24h, Last 7d, etc.)
- Support custom date range picker
- Propagate filter to all panels

**Acceptance Criteria:**
- Date filter UI is intuitive
- All panels update when filter changes
- Custom date ranges work correctly

---

### Phase 3: Panel Components & Interactivity (Steps 21-30)

#### Step 21: Time Series Panel Component
- Create `TimeSeriesPanel.tsx` with Plotly.js
- Render line charts from API data
- Support multiple series
- Add hover tooltips
- Handle loading and error states

**Acceptance Criteria:**
- Time series plots render correctly
- Multiple lines show with different colors
- Loading spinner appears during fetch
- Errors display helpful messages

#### Step 22: KPI Panel Component
- Create `KPIPanel.tsx`
- Display large metric value
- Color-code based on thresholds
- Show unit and label
- Add trend indicator (optional)

**Acceptance Criteria:**
- KPI value displays prominently
- Color changes based on threshold
- Component is visually appealing

#### Step 23: Health Status Panel Component
- Create `HealthStatusPanel.tsx`
- Display list of services with status dots
- Color-code red/amber/green
- Show last check timestamp
- Display error messages on hover

**Acceptance Criteria:**
- Services display with correct status colors
- Timestamps are human-readable
- Error details appear on hover

#### Step 24: Table Panel Component
- Create `TablePanel.tsx` with TanStack Table
- Implement sorting
- Implement pagination
- Add column filtering (optional)
- Make responsive

**Acceptance Criteria:**
- Table displays data correctly
- Sorting works on all columns
- Pagination controls work
- Mobile view is usable

#### Step 25: Panel Click-Through / Drill Down
- Create `DrillDownModal.tsx` component
- Implement full-screen modal for panels
- Show expanded chart + data table
- Add "Disable Aggregation" toggle for time series
- Add export functionality (CSV)

**Acceptance Criteria:**
- Clicking panel opens drill-down
- Full-screen chart renders correctly
- Aggregation toggle works
- Export downloads CSV file

#### Step 26: Auto-Refresh Mechanism
- Implement panel-level refresh timers
- Use TanStack Query's refetch intervals
- Add manual refresh button
- Show last updated timestamp

**Acceptance Criteria:**
- Panels auto-refresh per config
- Manual refresh button works
- Last updated time displays

#### Step 27: In-Memory Caching
- Implement simple LRU cache in `cache.py`
- Cache panel data responses
- Set TTL based on refresh interval
- Invalidate on date filter change

**Acceptance Criteria:**
- Cached responses return faster
- Cache respects TTL
- Cache size is bounded

#### Step 28: Error Handling & Loading States
- Add global error boundary (React)
- Implement retry logic for failed API calls
- Show skeleton loaders during data fetch
- Display user-friendly error messages

**Acceptance Criteria:**
- Failed API calls retry automatically
- Errors don't crash the app
- Loading states are clear

#### Step 29: Mobile Responsiveness
- Make header responsive
- Stack panels vertically on mobile
- Optimize touch interactions
- Test on various screen sizes

**Acceptance Criteria:**
- Dashboard works on mobile devices
- All interactions are touch-friendly
- No horizontal scrolling required

#### Step 30: Custom Image Panel Support
- Add `/api/v1/custom/:endpoint` route handler
- Support custom Python functions returning images
- Create `CustomImagePanel.tsx` component
- Display images with loading states

**Acceptance Criteria:**
- Custom endpoints can return PNG/SVG images
- Images display in panels
- Errors handled gracefully

---

### Phase 4: Custom Panels & Reports (Steps 31-35)

#### Step 31: Custom Template Panel Support
- Extend custom endpoint for JSON responses
- Implement simple template rendering (Jinja2-like in TypeScript)
- Create `CustomTemplatePanel.tsx`
- Support basic interpolation and loops

**Acceptance Criteria:**
- Custom endpoints return JSON
- Templates render with interpolated data
- Basic control structures work

#### Step 32: Custom Panel Registration System
- Create Python decorator for registering custom panels
- Auto-discover custom panels in `custom_panels/` directory
- Document how to add custom panels
- Provide example custom panel

**Acceptance Criteria:**
- Custom panels register automatically
- Example panel works end-to-end
- Documentation is clear

#### Step 33: Reports Page
- Create `/reports/:panel_id` route
- Display single panel in full-page view
- Remove dashboard chrome
- Add export button
- Support direct links to reports

**Acceptance Criteria:**
- Report page displays single panel
- URL is shareable
- Export works

#### Step 34: Multiple Dashboards per Tenant
- Support multiple dashboard configs per tenant
- Add dashboard selector dropdown
- Update routing to support dashboard names
- Default to `default.yaml` dashboard

**Acceptance Criteria:**
- Tenants can have multiple dashboards
- Dashboard selector works
- URLs include dashboard name

#### Step 35: Configuration Validation CLI
- Create CLI tool to validate YAML configs
- Check for required fields
- Validate SQL queries (syntax only)
- Report errors with file and line numbers

**Acceptance Criteria:**
- `uv run validate-configs` checks all YAML files
- Invalid configs are reported clearly
- Tool exits with error code on failure

---

### Phase 5: Testing & Quality (Steps 36-42)

#### Step 36: Backend Unit Tests - Config Loader
- Write tests for YAML parsing
- Test validation errors
- Test caching behavior
- Mock filesystem for tests

**Acceptance Criteria:**
- Tests cover all config types
- Invalid configs raise expected errors
- Tests run quickly with mocks

#### Step 37: Backend Unit Tests - Query Builder & Aggregation
- Test SQL query generation
- Test time-bucket aggregation logic
- Test date range calculations
- Test SQL injection prevention

**Acceptance Criteria:**
- Queries are validated for correctness
- Aggregation math is verified
- SQL injection attempts fail tests

#### Step 38: Backend Integration Tests - API Endpoints
- Test all API endpoints with httpx
- Use test database fixtures
- Test authentication flows
- Test multi-tenancy isolation

**Acceptance Criteria:**
- All endpoints return correct responses
- Tenant data is isolated
- Auth required for protected routes

#### Step 39: Frontend Unit Tests - Components
- Test panel components with Vitest
- Test date filter logic
- Test drill-down modal
- Mock API calls

**Acceptance Criteria:**
- Components render without errors
- User interactions trigger expected behavior
- Coverage > 70% for components

#### Step 40: End-to-End Tests with Playwright
- Write E2E test for login flow
- Write E2E test for dashboard loading
- Write E2E test for panel interactions
- Write E2E test for drill-down

**Acceptance Criteria:**
- E2E tests run in CI
- Tests cover critical user paths
- Tests are reliable (no flakiness)

#### Step 41: GitHub Actions CI Pipeline
- Set up workflow for backend tests
- Set up workflow for frontend tests
- Set up linting checks (ruff, mypy, eslint)
- Set up E2E tests
- Add Docker build validation

**Acceptance Criteria:**
- CI runs on every PR
- All checks must pass before merge
- Build artifacts are cached

#### Step 42: Performance Testing & Optimization
- Load test API endpoints
- Profile database queries
- Optimize slow queries with indexes
- Test with large datasets (100k+ rows)
- Measure frontend bundle size

**Acceptance Criteria:**
- API responds < 500ms for typical queries
- Aggregated queries handle 1M+ rows
- Frontend bundle < 500KB gzipped

---

### Phase 6: Documentation & Deployment (Steps 43-47)

#### Step 43: API Documentation
- Ensure OpenAPI docs are comprehensive
- Add examples to all endpoints
- Document authentication flow
- Add postman/curl examples

**Acceptance Criteria:**
- `/docs` endpoint has full API documentation
- Authentication is clearly explained
- Examples work copy-paste

#### Step 44: Configuration Guide
- Document YAML schema for all panel types
- Provide examples for each panel type
- Explain aggregation rules
- Document custom panel creation

**Acceptance Criteria:**
- New developers can create panels from docs
- All config options are documented
- Examples are copy-pasteable

#### Step 45: Deployment Guide
- Document Docker Compose setup for production
- Document environment variable configuration
- Explain database setup and migrations
- Document Keycloak configuration
- Provide SSL/TLS setup guide

**Acceptance Criteria:**
- System can be deployed from docs alone
- All environment variables documented
- Security best practices included

#### Step 46: Developer Setup Guide
- Document local development setup
- Explain project structure
- Provide troubleshooting section
- Document how to run tests

**Acceptance Criteria:**
- New developers can set up in < 30 minutes
- Common issues are addressed
- Testing instructions are clear

#### Step 47: Production Deployment & Monitoring
- Set up production Docker Compose
- Configure nginx reverse proxy
- Set up SSL certificates
- Add application logging
- Create basic monitoring dashboard (using the system itself!)
- Document backup procedures

**Acceptance Criteria:**
- System runs in production
- HTTPS enabled
- Logs are accessible
- Backups can be restored

---

## Testing Strategy

### Unit Tests
- All services in `backend/app/services/` must have > 80% coverage
- All utility functions must be tested
- Configuration parsing must be thoroughly tested
- Frontend utilities and helpers must be tested

### Integration Tests
- All API endpoints must have integration tests
- Database operations must be tested with test fixtures
- Multi-tenancy isolation must be verified

### End-to-End Tests
- Critical user paths:
  1. Login → Select Tenant → View Dashboard
  2. Filter by Date → View Updated Panels
  3. Click Panel → Drill Down → Export Data
  4. Admin → Create User → Assign Tenant

### Performance Tests
- API endpoints with 100 concurrent requests
- Database queries with 1M+ rows
- Frontend rendering with 20+ panels

## Security Considerations

### Authentication
- All API endpoints except `/health` require authentication
- JWT tokens expire after configurable period
- Refresh tokens supported via Keycloak

### Authorization
- Users can only access data for their assigned tenants
- Admin endpoints check `is_admin` flag
- Tenant database connections isolated per request

### SQL Injection Prevention
- All queries use parameterized statements
- Table/column names validated against whitelist from config
- User input never directly concatenated into SQL

### Data Privacy
- Tenant data never crosses database boundaries
- API responses filtered by tenant context
- Audit logging for admin actions

## Performance Targets

- **API Response Time**: < 500ms for p95
- **Dashboard Load Time**: < 2 seconds for initial render
- **Panel Refresh**: < 1 second per panel
- **Database Queries**: < 200ms for aggregated queries
- **Concurrent Users**: Support 50+ concurrent users per tenant
- **Data Volume**: Handle 10M+ rows per tenant database

## Maintenance & Extensibility

### Adding a New Panel Type
1. Create panel config schema in `schemas/panel.py`
2. Implement panel handler in `services/panel_factory.py`
3. Create React component in `frontend/src/components/panels/`
4. Add example YAML config
5. Update documentation

### Adding a New Tenant
1. Create PostgreSQL database
2. Run migrations (if shared schema)
3. Add tenant to central database
4. Create config folder in `config/tenants/{tenant-id}/`
5. Add dashboard and panel YAML files
6. Assign users to tenant

### Adding a Custom Panel
1. Create Python file in `backend/app/custom_panels/`
2. Implement endpoint handler with `@custom_panel` decorator
3. Add YAML config referencing custom endpoint
4. Optionally create custom React component

## Future Enhancements (Out of Scope)

- Alert notifications (email, Slack, PagerDuty)
- Dashboard sharing with external users
- PDF report generation
- Mobile native apps
- Real-time WebSocket updates
- Advanced analytics (anomaly detection, forecasting)
- Role-based access control within tenants
- Dashboard versioning and rollback

## Glossary

- **Tenant**: An isolated organization or team with their own database and dashboards
- **Panel**: A single visualization or data display component on a dashboard
- **Dashboard**: A collection of panels arranged in a grid layout
- **Report**: A standalone view of a single panel or table
- **Drill-down**: Expanding a panel to full-screen with detailed data
- **Aggregation**: Time-based bucketing and averaging of data for performance
- **KPI**: Key Performance Indicator, a single metric display
- **Health Status**: Red/Amber/Green status indicator for services

## Success Criteria

The project is considered complete when:

1. ✅ All 47 implementation steps are complete
2. ✅ All tests pass (unit, integration, E2E)
3. ✅ CI/CD pipeline is green
4. ✅ Code coverage > 70% for backend and frontend
5. ✅ Documentation is complete and reviewed
6. ✅ System is deployed to production environment
7. ✅ At least 2 tenants are using the system successfully
8. ✅ Performance targets are met under load testing
9. ✅ Security audit completed (basic checklist)
10. ✅ Handoff to maintenance team completed

---

## Appendix: Key Commands

### Development
```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend  
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests
uv run pytest
npm run test
npx playwright test

# Linting
uv run ruff check .
uv run mypy .
npm run lint
```

### Production
```bash
# Build
docker-compose -f docker-compose.prod.yml build

# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Migrations
uv run alembic upgrade head

# Validate configs
uv run python -m app.cli validate-configs
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-08  
**Author**: System Specification  
**Status**: Ready for Implementation
