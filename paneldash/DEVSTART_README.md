# PanelDash Development Environment Setup

## Overview

The `devstart.py` script provides a complete, automated development environment for PanelDash that includes:

- **Keycloak** - OAuth2/OIDC authentication server with pre-configured realm and users
- **PostgreSQL** - Local database using pgserver
- **Backend API** - FastAPI application with database migrations
- **Frontend** - React/Vite development server (optional)

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Java 17+ (for Keycloak)

## Quick Start

```bash
cd paneldash
python3 devstart.py
```

This will:
1. Download and configure Keycloak (first run only)
2. Start a local PostgreSQL database
3. Run database migrations
4. Start the backend API on http://localhost:8001
5. Start the frontend on http://localhost:5173

## Usage

### Basic Commands

```bash
# Start all services (including frontend)
python3 devstart.py

# Start without frontend (backend and auth only)
python3 devstart.py --no-frontend

# Use custom Keycloak port
python3 devstart.py --keycloak-port 9080
```

### Services and Ports

After startup, the following services will be available:

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | See test users below |
| Backend API | http://localhost:8001 | N/A |
| API Docs | http://localhost:8001/docs | N/A |
| Keycloak | http://localhost:8080 | admin / admin |
| Keycloak Admin | http://localhost:8080/admin | admin / admin |
| PostgreSQL | Unix socket (see logs) | postgres (no password) |

### Test Users

The script automatically creates two test users in Keycloak:

**Regular User:**
- Username: `testuser`
- Password: `testpass`
- Roles: `user`

**Admin User:**
- Username: `adminuser`
- Password: `adminpass`
- Roles: `user`, `admin`

### OAuth Clients

Two OAuth clients are pre-configured:

**Frontend Client** (`paneldash-frontend`):
- Type: Public client
- Redirect URIs: `http://localhost:5173/*`, `http://localhost:5174/*`
- Web Origins: `http://localhost:5173`, `http://localhost:5174`

**Backend API Client** (`paneldash-api`):
- Type: Confidential client
- Secret: `your-api-client-secret`
- Direct access grants enabled

## Testing the Setup

### Manual Testing

1. Start the development environment:
   ```bash
   python3 devstart.py
   ```

2. Open http://localhost:5173 in your browser

3. Click "Sign in with Keycloak"

4. Log in with `testuser` / `testpass`

5. You should be redirected to the dashboard

### Automated Testing with Playwright

The repository includes Playwright tests to verify the complete login flow:

```bash
# Install Playwright browsers (first time only)
npx playwright install chromium

# Run the login flow tests
npx playwright test tests/e2e/specs/keycloak-login.spec.ts \
  --config=playwright.devstart.config.ts
```

The tests will:
- Navigate to the application
- Complete the Keycloak login flow
- Verify successful authentication
- Check for redirect loops
- Capture screenshots for debugging

Test results and screenshots are saved to `test-results/`.

## Architecture

### Component Interaction

```
┌─────────────┐         ┌──────────────┐
│   Frontend  │────────▶│   Keycloak   │
│  (React)    │◀────────│   (AuthN)    │
└──────┬──────┘         └──────────────┘
       │
       │ HTTP + JWT
       ▼
┌─────────────┐         ┌──────────────┐
│   Backend   │────────▶│  PostgreSQL  │
│  (FastAPI)  │         │  (pgserver)  │
└─────────────┘         └──────────────┘
```

### Authentication Flow

1. User navigates to frontend
2. Frontend initializes Keycloak JS client
3. If not authenticated, redirect to Keycloak login page
4. User enters credentials
5. Keycloak validates and issues tokens
6. Frontend receives tokens via redirect
7. Frontend includes JWT in API requests
8. Backend validates JWT with Keycloak public keys

## Known Issues and Debugging

### Issue: Frontend doesn't redirect to Keycloak login

**Symptoms:** Frontend goes directly to dashboard without authentication

**Root Cause:** The AuthContext initializes Keycloak with `onLoad: 'check-sso'` which doesn't force authentication.

**Debug Steps:**
1. Open browser console (F12)
2. Check for Keycloak initialization messages
3. Look for errors about CORS or 3p-cookies
4. Verify localStorage is clean: `localStorage.clear()`

**Potential Fixes:**
- Change Keycloak init to use `onLoad: 'login-required'`
- Ensure no E2E test tokens in localStorage
- Check that redirect URIs match exactly

### Issue: Silent SSO check fails

**Symptoms:** Console shows errors about `3p-cookies/step1.html`

**Solution:** The `silent-check-sso.html` file should exist in `frontend/public/`. It's included in the repository.

### Issue: CORS errors

**Symptoms:** Browser console shows CORS policy violations

**Solution:**
- Verify Keycloak web origins include `http://localhost:5173`
- Check that backend CORS middleware is configured correctly
- Ensure all URLs use the same protocol (http vs https)

### Issue: Backend can't connect to Keycloak

**Symptoms:** Backend logs show connection errors to Keycloak

**Solution:**
- Check Keycloak is running: `curl http://localhost:8080/health`
- Verify `KEYCLOAK_SERVER_URL` environment variable
- Check firewall rules aren't blocking connections

## Development Workflow

### Making Frontend Changes

The frontend uses Vite HMR (Hot Module Replacement), so changes are reflected immediately without restart.

### Making Backend Changes

The backend runs with `--reload`, so changes to Python files trigger an automatic restart.

### Database Changes

To create a new migration:

```bash
cd backend
uv run alembic revision --autogenerate -m "Description of changes"
uv run alembic upgrade head
```

### Keycloak Configuration Changes

To modify realm settings:
1. Open http://localhost:8080/admin
2. Log in with `admin` / `admin`
3. Select the `paneldash` realm
4. Make your changes

Note: Changes made through the admin console are not persisted in code. To make permanent changes, modify the realm configuration in `devstart.py`.

## Cleaning Up

To stop all services, press `Ctrl+C` in the terminal running `devstart.py`.

The script automatically cleans up:
- Kills all spawned processes
- Stops PostgreSQL
- Stops Keycloak

Temporary files are stored in:
- PostgreSQL: `/tmp/paneldash-dev-db-*`
- Keycloak: `~/.keycloak-test/`
- Keycloak data: `./keycloak-dev-server/`

To completely clean the environment:

```bash
rm -rf ~/.keycloak-test
rm -rf ./keycloak-dev-server
rm -rf /tmp/paneldash-dev-db-*
```

## Troubleshooting

### Port Already in Use

If you get "port already in use" errors:

```bash
# Find and kill process on port 8080 (Keycloak)
lsof -ti:8080 | xargs kill -9

# Find and kill process on port 8001 (Backend)
lsof -ti:8001 | xargs kill -9

# Find and kill process on port 5173 (Frontend)
lsof -ti:5173 | xargs kill -9
```

### Python Dependencies

Install additional dependencies if needed:

```bash
pip install httpx pgserver pytest-keycloak-fixture
```

### Node Dependencies

If frontend dependencies are missing:

```bash
cd frontend
npm install
```

## Additional Resources

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Playwright Documentation](https://playwright.dev/)

## Contributing

When making changes to the dev environment setup:

1. Test the changes with a clean environment
2. Update this README
3. Update the Playwright tests if authentication flow changes
4. Document any new environment variables or configuration options
