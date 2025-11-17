
export CENTRAL_DB_HOST=/tmp/paneldash-dev-db-ae_g7az5 #this changes all the time?!
export CENTRAL_DB_PORT=5432
export CENTRAL_DB_NAME=paneldash_central
export CENTRAL_DB_USER=postgres
export CENTRAL_DB_PASSWORD=
export KEYCLOAK_SERVER_URL=http://localhost:8080
export KEYCLOAK_REALM=paneldash
export KEYCLOAK_CLIENT_ID=paneldash-api
export KEYCLOAK_CLIENT_SECRET=your-api-client-secret
export DEBUG=true


#["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--log-level=debug"],

uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-level=debug