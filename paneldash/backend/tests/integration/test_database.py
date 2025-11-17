"""Integration tests for database migrations and schema."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

# Marker for tests that require a database
pytestmark = pytest.mark.integration


class TestDatabaseMigrations:
    """Tests for database migrations."""

    @pytest.mark.asyncio
    async def test_database_connection(self, test_db: None, test_db_url: str) -> None:  # noqa: ARG002
        """Test that we can connect to the database."""
        engine = create_async_engine(test_db_url, echo=False)

        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                assert row is not None
                assert row[0] == 1
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_schema_exists(self, test_db: None, test_db_url: str) -> None:  # noqa: ARG002
        """Test that the expected tables exist in the database."""
        engine = create_async_engine(test_db_url, echo=False)

        try:
            async with engine.begin() as conn:
                # Run synchronously within the async context
                def check_schema(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)
                    tables = inspector.get_table_names()
                    return tables

                tables = await conn.run_sync(check_schema)

                # These tables should exist after migration 001
                expected_tables = ["users", "tenants", "user_tenants"]

                # Verify the expected tables exist
                for table in expected_tables:
                    assert table in tables, f"Table '{table}' not found in database"

                # Verify users table structure
                def check_users_columns(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)
                    columns = inspector.get_columns("users")
                    column_names = [col["name"] for col in columns]
                    return column_names

                users_columns = await conn.run_sync(check_users_columns)
                expected_columns = [
                    "id",
                    "keycloak_id",
                    "email",
                    "full_name",
                    "is_admin",
                    "created_at",
                    "updated_at",
                ]
                for col in expected_columns:
                    assert (
                        col in users_columns
                    ), f"Column '{col}' not found in users table"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_constraints(self, test_db: None, test_db_url: str) -> None:  # noqa: ARG002
        """Test that database constraints are properly set up."""
        engine = create_async_engine(test_db_url, echo=False)

        try:
            async with engine.begin() as conn:

                def check_constraints(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)

                    # Check primary keys
                    pk_users = inspector.get_pk_constraint("users")
                    pk_tenants = inspector.get_pk_constraint("tenants")
                    pk_user_tenants = inspector.get_pk_constraint("user_tenants")

                    # Check foreign keys
                    fk_user_tenants = inspector.get_foreign_keys("user_tenants")

                    return {
                        "pk_users": pk_users,
                        "pk_tenants": pk_tenants,
                        "pk_user_tenants": pk_user_tenants,
                        "fk_user_tenants": fk_user_tenants,
                    }

                constraints = await conn.run_sync(check_constraints)

                # Verify primary keys
                assert "id" in constraints["pk_users"]["constrained_columns"]
                assert "id" in constraints["pk_tenants"]["constrained_columns"]
                assert set(constraints["pk_user_tenants"]["constrained_columns"]) == {
                    "user_id",
                    "tenant_id",
                }

                # Verify foreign keys exist
                assert (
                    len(constraints["fk_user_tenants"]) == 2
                ), "user_tenants should have 2 foreign keys"

                # Check that foreign keys reference correct tables
                fk_tables = {
                    fk["referred_table"] for fk in constraints["fk_user_tenants"]
                }
                assert fk_tables == {"users", "tenants"}
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_indexes(self, test_db: None, test_db_url: str) -> None:  # noqa: ARG002
        """Test that database indexes are properly created."""
        engine = create_async_engine(test_db_url, echo=False)

        try:
            async with engine.begin() as conn:

                def check_indexes(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)

                    users_indexes = inspector.get_indexes("users")
                    tenants_indexes = inspector.get_indexes("tenants")
                    user_tenants_indexes = inspector.get_indexes("user_tenants")

                    return {
                        "users": users_indexes,
                        "tenants": tenants_indexes,
                        "user_tenants": user_tenants_indexes,
                    }

                indexes = await conn.run_sync(check_indexes)

                # We should have indexes on email, tenant_id, and foreign keys
                # Note: Exact index names may vary, so we check for indexed columns
                users_index_cols = {
                    tuple(idx["column_names"]) for idx in indexes["users"]
                }

                # Check that we have an index on email
                assert any(
                    "email" in cols for cols in users_index_cols
                ), "Should have index on users.email"
        finally:
            await engine.dispose()
