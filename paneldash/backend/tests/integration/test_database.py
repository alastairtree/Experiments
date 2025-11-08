"""Integration tests for database migrations and schema.

Note: These tests require a running PostgreSQL database.
They will be skipped if the database is not available.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

# Marker for tests that require a database
pytestmark = pytest.mark.integration


class TestDatabaseMigrations:
    """Tests for database migrations."""

    @pytest.mark.asyncio
    async def test_database_connection(self, db_available: bool) -> None:
        """Test that we can connect to the database."""
        if not db_available:
            pytest.skip("Database is not available")

        engine = create_async_engine(settings.central_database_url, echo=False)

        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                assert row is not None
                assert row[0] == 1
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_schema_exists(self, db_available: bool) -> None:
        """Test that the expected tables exist in the database.

        Note: This test assumes migrations have been run manually.
        In a full CI environment, you would run migrations before tests.
        """
        if not db_available:
            pytest.skip("Database is not available")

        engine = create_async_engine(settings.central_database_url, echo=False)

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

                # Check if we have any tables (might not if migrations haven't run)
                if len(tables) > 0:
                    # If we have tables, verify the expected ones exist
                    for table in expected_tables:
                        assert table in tables, f"Table '{table}' not found in database"

                    # Verify users table structure
                    def check_users_columns(sync_conn):  # type: ignore[no-untyped-def]
                        inspector = inspect(sync_conn)
                        columns = inspector.get_columns("users")
                        column_names = [col["name"] for col in columns]
                        return column_names

                    users_columns = await conn.run_sync(check_users_columns)
                    expected_columns = ["id", "keycloak_id", "email", "full_name",
                                       "is_admin", "created_at", "updated_at"]
                    for col in expected_columns:
                        assert col in users_columns, f"Column '{col}' not found in users table"
                else:
                    # If no tables exist, that's okay - migrations need to be run manually
                    # We'll just skip the detailed checks
                    pytest.skip("Database has no tables - migrations need to be run manually")
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_constraints(self, db_available: bool) -> None:
        """Test that database constraints are properly set up."""
        if not db_available:
            pytest.skip("Database is not available")

        engine = create_async_engine(settings.central_database_url, echo=False)

        try:
            async with engine.begin() as conn:
                def check_constraints(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)

                    # Check if tables exist first
                    tables = inspector.get_table_names()
                    if "users" not in tables:
                        return None

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

                if constraints is None:
                    pytest.skip("Database has no tables - migrations need to be run manually")
                    return

                # Verify primary keys
                assert "id" in constraints["pk_users"]["constrained_columns"]
                assert "id" in constraints["pk_tenants"]["constrained_columns"]
                assert set(constraints["pk_user_tenants"]["constrained_columns"]) == {
                    "user_id",
                    "tenant_id"
                }

                # Verify foreign keys exist
                assert len(constraints["fk_user_tenants"]) == 2, \
                    "user_tenants should have 2 foreign keys"

                # Check that foreign keys reference correct tables
                fk_tables = {fk["referred_table"] for fk in constraints["fk_user_tenants"]}
                assert fk_tables == {"users", "tenants"}
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_database_indexes(self, db_available: bool) -> None:
        """Test that database indexes are properly created."""
        if not db_available:
            pytest.skip("Database is not available")

        engine = create_async_engine(settings.central_database_url, echo=False)

        try:
            async with engine.begin() as conn:
                def check_indexes(sync_conn):  # type: ignore[no-untyped-def]
                    inspector = inspect(sync_conn)

                    # Check if tables exist first
                    tables = inspector.get_table_names()
                    if "users" not in tables:
                        return None

                    users_indexes = inspector.get_indexes("users")
                    tenants_indexes = inspector.get_indexes("tenants")
                    user_tenants_indexes = inspector.get_indexes("user_tenants")

                    return {
                        "users": users_indexes,
                        "tenants": tenants_indexes,
                        "user_tenants": user_tenants_indexes,
                    }

                indexes = await conn.run_sync(check_indexes)

                if indexes is None:
                    pytest.skip("Database has no tables - migrations need to be run manually")
                    return

                # We should have indexes on email, tenant_id, and foreign keys
                # Note: Exact index names may vary, so we check for indexed columns
                users_index_cols = {
                    tuple(idx["column_names"]) for idx in indexes["users"]
                }

                # Check that we have an index on email
                assert any("email" in cols for cols in users_index_cols), \
                    "Should have index on users.email"
        finally:
            await engine.dispose()
