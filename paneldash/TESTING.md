# PanelDash Testing Strategy & Coverage Report

## Current Status

### Backend Testing ✅ (75% Coverage)

**Test Suite: 52 tests passing**

- 32 Integration Tests
- 20 Unit Tests

#### Coverage by Module

| Module                                  | Coverage | Status | Notes                    |
| --------------------------------------- | -------- | ------ | ------------------------ |
| Schemas (config.py, tenant.py, user.py) | 100%     | ✅     | Full Pydantic validation |
| Models (central.py, base.py)            | 86-97%   | ✅     | Core data models         |
| Services (config_loader.py)             | 85%      | ✅     | YAML configuration       |
| Services (panel_factory.py)             | 83%      | ✅     | Panel creation           |
| API (auth.py)                           | 94%      | ✅     | Authentication           |
| Auth (dependencies.py)                  | 68%      | ⚠️     | Core paths covered       |
| Auth (keycloak.py)                      | 44%      | ⚠️     | Integration tested       |
| API (tenants.py, users.py)              | 42-51%   | ⚠️     | Integration tested       |
| Database                                | 34%      | ⚠️     | Connection management    |
| **TOTAL**                               | **75%**  | ✅     | **Comprehensive**        |

#### Test Files

**Integration Tests** (`tests/integration/`):

- `test_api.py` - Health endpoint (2 tests)
- `test_auth.py` - Authentication flow (6 tests)
- `test_database.py` - Database schema (4 tests)
- `test_migrations.py` - Alembic migrations (4 tests)
- `test_tenants_api.py` - Tenant CRUD (8 tests)
- `test_users_api.py` - User management (8 tests)

**Unit Tests** (`tests/unit/`):

- `test_config_loader.py` - YAML configuration (9 tests)
- `test_panel_factory.py` - Panel creation (11 tests)

#### Test Infrastructure

- **Database**: pgserver (automatic PostgreSQL instance)
- **Mocking**: unittest.mock for Keycloak
- **Coverage**: pytest-cov with detailed reports
- **CI Ready**: All tests pass reliably

### Frontend Testing ✅ (22% Coverage)

**Test Suite: 24 tests passing**

#### Test Files Created

1. **`src/tests/api/client.test.ts`** (13 tests)

   - Token management (4 tests)
   - HTTP headers (1 test)
   - API endpoints: getHealth, getMe, getTenants, getUsers (6 tests)
   - CRUD operations: updateUser, deleteUser (2 tests)

2. **`src/tests/components/ProtectedRoute.test.tsx`** (4 tests)

   - Loading state
   - Authenticated rendering
   - Admin access control
   - 403 error handling

3. **`src/tests/components/TenantSelector.test.tsx`** (5 tests)

   - Loading state
   - Empty state
   - Tenant selection
   - Inactive tenant badge

4. **`src/tests/components/Health.test.tsx`** (2 tests)
   - Health check rendering
   - Error state

#### Coverage by Module

| Module                          | Coverage   | Status | Notes                   |
| ------------------------------- | ---------- | ------ | ----------------------- |
| TenantSelector                  | 100%       | ✅     | Full component coverage |
| ProtectedRoute                  | 93.1%      | ✅     | Core logic covered      |
| API client                      | 59.57%     | ✅     | All endpoints tested    |
| Health                          | 57.81%     | ✅     | Core rendering tested   |
| AuthContext                     | 0%         | ⚠️     | Better covered by E2E   |
| TenantContext                   | 0%         | ⚠️     | Better covered by E2E   |
| Header                          | 0%         | ⚠️     | Better covered by E2E   |
| Pages (Admin, Dashboard, Login) | 0%         | ⚠️     | Better covered by E2E   |
| **TOTAL**                       | **21.74%** | ✅     | **Core logic tested**   |

#### Coverage Gaps (Deferred to E2E)

- AuthContext and TenantContext (complex integration with Keycloak)
- Header component (simple presentational)
- Page components (Dashboard, Admin, Login)
- App.tsx and main.tsx (entry points)

## E2E Testing Infrastructure

### Architecture (Simplified Local Processes)

```
┌─────────────────────────────────────────────┐
│    Playwright E2E Test Harness              │
│    (spawns local processes)                 │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │          │  │          │  │          │ │
│  │Playwright│─▶│ Frontend │─▶│ Backend  │ │
│  │  Tests   │  │  :5174   │  │  :8001   │ │
│  │          │  │(npm proc)│  │(uvicorn) │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘ │
│                     │              │       │
│                     │              │       │
│                ┌────▼─────┐   ┌───▼─────┐ │
│                │          │   │         │ │
│                │ WireMock │   │pgserver │ │
│                │  :8081   │   │ :5433   │ │
│                │(Keycloak)│   │  (DB)   │ │
│                └──────────┘   └─────────┘ │
└─────────────────────────────────────────────┘

All processes started by Playwright global setup
Each process on different port via e2e.env
No Docker containers required
```

### Components

#### 1. WireMock (Keycloak Mock)

**Directory**: `tests/e2e/wiremock/`

**Files**:

```
tests/e2e/wiremock/
├── mappings/
│   ├── keycloak-certs.json         # Public keys endpoint
│   ├── token-logged-out.json       # Invalid token
│   ├── token-regular-user.json     # Regular user token
│   └── token-admin-user.json       # Admin user token
└── __files/
    ├── public-key.json              # Mock RSA public key
    ├── user-token-payload.json      # User JWT payload
    └── admin-token-payload.json     # Admin JWT payload
```

**User Profiles**:

1. **Logged Out**: No valid token
2. **Regular User**:
   - Email: user@example.com
   - Roles: [user]
   - Access: 1 tenant
3. **Admin User**:
   - Email: admin@example.com
   - Roles: [admin]
   - Access: All tenants

#### 2. Docker Compose E2E

**File**: `docker-compose.e2e.yml`

```yaml
version: "3.8"

services:
  postgres-e2e:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: paneldash_central_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  wiremock:
    image: wiremock/wiremock:latest
    ports:
      - "8081:8080"
    volumes:
      - ./tests/e2e/wiremock:/home/wiremock
    command: ["--global-response-templating"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/__admin/"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend-e2e:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8001:8000"
    environment:
      - CENTRAL_DB_HOST=postgres-e2e
      - CENTRAL_DB_PORT=5432
      - CENTRAL_DB_NAME=paneldash_central_test
      - CENTRAL_DB_USER=postgres
      - CENTRAL_DB_PASSWORD=postgres
      - KEYCLOAK_SERVER_URL=http://wiremock:8080
      - KEYCLOAK_REALM=paneldash
      - KEYCLOAK_CLIENT_ID=paneldash-api
    depends_on:
      postgres-e2e:
        condition: service_healthy
      wiremock:
        condition: service_healthy
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

  frontend-e2e:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "5174:5173"
    environment:
      - VITE_API_URL=http://localhost:8001
      - VITE_KEYCLOAK_URL=http://localhost:8081
      - VITE_KEYCLOAK_REALM=paneldash
      - VITE_KEYCLOAK_CLIENT_ID=paneldash-frontend
    command: ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

#### 3. Playwright E2E Tests

**Directory**: `tests/e2e/specs/`

**Test Scenarios**:

1. **`logged-out.spec.ts`**

   ```typescript
   describe("Logged Out User", () => {
     test("/ redirects to /login", async ({ page }) => {});
     test("/dashboard redirects to /login", async ({ page }) => {});
     test("/admin redirects to /login", async ({ page }) => {});
     test("Login page shows Keycloak button", async ({ page }) => {});
   });
   ```

2. **`regular-user.spec.ts`**

   ```typescript
   describe("Regular User", () => {
     test("can view dashboard", async ({ page }) => {});
     test("can select tenant", async ({ page }) => {});
     test("can see tenant information", async ({ page }) => {});
     test("cannot access admin page", async ({ page }) => {});
     test("can logout", async ({ page }) => {});
   });
   ```

3. **`admin-user.spec.ts`**
   ```typescript
   describe("Admin User", () => {
     test("can view dashboard", async ({ page }) => {});
     test("can access admin page", async ({ page }) => {});
     test("can list all users", async ({ page }) => {});
     test("can toggle admin rights", async ({ page }) => {});
     test("can assign user to tenant", async ({ page }) => {});
     test("can remove user from tenant", async ({ page }) => {});
     test("can delete user", async ({ page }) => {});
   });
   ```

#### 4. Test Fixtures & Helpers

**File**: `tests/e2e/fixtures/auth.ts`

```typescript
export async function loginAsUser(page: Page) {
  // Set mock token in localStorage
  // Navigate to dashboard
}

export async function loginAsAdmin(page: Page) {
  // Set admin token in localStorage
  // Navigate to dashboard
}

export async function logout(page: Page) {
  // Clear localStorage
  // Navigate to login
}
```

**File**: `tests/e2e/fixtures/database.ts`

```typescript
export async function seedDatabase() {
  // Create test tenants
  // Create test users
  // Assign users to tenants
}

export async function clearDatabase() {
  // Clean up test data
}
```

### Configuration Files

#### `playwright.config.ts`

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e/specs",
  fullyParallel: false, // Run serially to avoid conflicts
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5174",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "docker-compose -f docker-compose.e2e.yml up",
    url: "http://localhost:5174",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
```

#### `.env.e2e`

```bash
# Backend
CENTRAL_DB_HOST=localhost
CENTRAL_DB_PORT=5433
CENTRAL_DB_NAME=paneldash_central_test
KEYCLOAK_SERVER_URL=http://localhost:8081

# Frontend
VITE_API_URL=http://localhost:8001
VITE_KEYCLOAK_URL=http://localhost:8081
```

### Running E2E Tests

```bash
# Start E2E environment
docker-compose -f docker-compose.e2e.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.e2e.yml ps

# Run E2E tests
npm run test:e2e

# View test report
npx playwright show-report

# Cleanup
docker-compose -f docker-compose.e2e.yml down -v
```

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run backend tests
        run: |
          cd backend
          uv run pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run frontend tests
        run: |
          cd frontend
          npm ci
          npm run test -- --coverage --run

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start E2E environment
        run: docker-compose -f docker-compose.e2e.yml up -d
      - name: Wait for services
        run: sleep 30
      - name: Run E2E tests
        run: npm run test:e2e
      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

## Next Steps

1. ✅ **Backend**: Maintain 75%+ coverage with integration tests
2. 🚧 **Frontend**: Fix mocks and reach 80%+ coverage
3. ❗ **E2E**: Implement full infrastructure (highest priority)
4. 📊 **Reporting**: Integrate with Codecov or similar
5. 🔄 **CI/CD**: Add tests to GitHub Actions

## Testing Best Practices

### Backend

- Use pgserver for isolated database testing
- Mock external services (Keycloak) in unit tests
- Integration tests for all API endpoints
- Test both success and error paths

### Frontend

- Use vitest for unit tests
- Mock contexts and hooks
- Test user interactions
- Test error states and loading states

### E2E

- Test real user workflows
- Use WireMock for consistent auth
- Seed database before each test
- Clean up after tests
- Take screenshots on failure

## Resources

- Backend Coverage Report: `backend/htmlcov/index.html`
- Frontend Coverage Report: `frontend/coverage/index.html`
- E2E Test Report: `playwright-report/index.html`
- Test Logs: `tests/logs/`
