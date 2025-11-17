"""Seed the database with development data."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text

from app.config import settings
from app.database import db_manager
from app.models.central import Tenant, User, UserTenant


async def seed_tenant_data(tenant: Tenant) -> None:
    """Seed tenant database with sample panel data.

    Args:
        tenant: The tenant to seed data for
    """
    print(f"🌱 Seeding tenant database for {tenant.name}...")

    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # 1. Create and populate metrics table (for timeseries and KPI panels)
        print("  Creating metrics table...")
        await session.execute(text("DROP TABLE IF EXISTS metrics"))
        await session.execute(
            text(
                """
                CREATE TABLE metrics (
                    recorded_at TIMESTAMP NOT NULL,
                    cpu_percent FLOAT NOT NULL,
                    memory_percent FLOAT NOT NULL,
                    server_name TEXT NOT NULL
                )
                """
            )
        )

        # Insert 100 records over the last 24 hours
        base_time = datetime.now() - timedelta(hours=24)
        servers = ["web-server-1", "web-server-2", "api-server-1"]

        for i in range(100):
            timestamp = base_time + timedelta(minutes=i * 15)  # Every 15 minutes
            for server in servers:
                # Simulate varying CPU usage (30-95%)
                cpu_value = 50.0 + (i % 45) + (hash(server) % 20)
                # Simulate varying memory usage (40-85%)
                memory_value = 60.0 + (i % 25) + (hash(server) % 15)

                await session.execute(
                    text(
                        "INSERT INTO metrics (recorded_at, cpu_percent, memory_percent, server_name) "
                        "VALUES (:ts, :cpu, :mem, :server)"
                    ),
                    {
                        "ts": timestamp,
                        "cpu": min(95.0, cpu_value),
                        "mem": min(85.0, memory_value),
                        "server": server,
                    },
                )

        print("  ✓ Created metrics table with 300 records")

        # 2. Create and populate health_status table
        print("  Creating health_status table...")
        await session.execute(text("DROP TABLE IF EXISTS health_status"))
        await session.execute(
            text(
                """
                CREATE TABLE health_status (
                    name TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    last_check TIMESTAMP NOT NULL
                )
                """
            )
        )

        # Insert health status for various services
        services = [
            ("api-gateway", 0),  # healthy
            ("database", 0),  # healthy
            ("cache-redis", 0),  # healthy
            ("queue-worker", 1),  # degraded
            ("backup-service", 0),  # healthy
        ]

        for service_name, status_value in services:
            await session.execute(
                text(
                    "INSERT INTO health_status (name, status, last_check) "
                    "VALUES (:name, :status, :ts)"
                ),
                {
                    "name": service_name,
                    "status": status_value,
                    "ts": datetime.now(),
                },
            )

        print("  ✓ Created health_status table with 5 services")

        # 3. Create and populate logs table (for table panels)
        print("  Creating logs table...")
        await session.execute(text("DROP TABLE IF EXISTS logs"))
        await session.execute(
            text(
                """
                CREATE TABLE logs (
                    timestamp TIMESTAMP NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    service TEXT NOT NULL
                )
                """
            )
        )

        # Insert 100 log entries
        severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        log_messages = [
            "Application started successfully",
            "Database connection established",
            "High memory usage detected",
            "Failed to connect to external API",
            "Request completed",
            "Cache miss occurred",
            "Authentication failed",
            "Rate limit exceeded",
            "Backup completed successfully",
            "Health check passed",
        ]

        for i in range(100):
            timestamp = datetime.now() - timedelta(minutes=i * 5)
            severity = severities[i % len(severities)]
            message = log_messages[i % len(log_messages)]
            service = servers[i % len(servers)]

            await session.execute(
                text(
                    "INSERT INTO logs (timestamp, message, severity, service) "
                    "VALUES (:ts, :msg, :sev, :service)"
                ),
                {
                    "ts": timestamp,
                    "msg": f"{message} (Entry #{i+1})",
                    "sev": severity,
                    "service": service,
                },
            )

        print("  ✓ Created logs table with 100 log entries")

        await session.commit()
        print(f"✅ Tenant {tenant.name} database seeded successfully!")


async def seed_database() -> None:
    """Seed the database with development data."""
    print("🌱 Seeding database with development data...")

    async with db_manager.get_central_session() as session:
        # Check if data already exists
        result = await session.execute(select(User))
        if result.scalars().first():
            print("⚠️  Database already contains data. Skipping seed.")
            return

        # Create test users matching Keycloak users from devstart.py
        print("Creating users...")

        # Admin user (matches adminuser from Keycloak)
        admin_user = User(
            keycloak_id=None,  # Will be replaced with real ID on first login
            email="admin@example.com",
            full_name="Admin User",
            is_admin=True,
        )
        session.add(admin_user)

        # Test user (matches testuser from Keycloak)
        test_user = User(
            keycloak_id=None,  # Will be replaced with real ID on first login
            email="testuser@example.com",
            full_name="Test User",
            is_admin=False,
        )
        session.add(test_user)

        await session.flush()  # Get IDs without committing
        print(f"✓ Created 2 users (admin: {admin_user.email}, test: {test_user.email})")

        # Create example tenant matching the tenant config in /tenants/example-tenant/
        print("Creating tenants...")
        example_tenant = Tenant(
            tenant_id="example-tenant",
            name="Example Tenant",
            # reuse the main app db for the demo tenant
            database_name=settings.central_db_name, #"tenant_example",
            database_host=settings.central_db_host,
            database_port=settings.central_db_port,
            database_user=settings.central_db_user,
            database_password=settings.central_db_password,
            is_active=True,
        )
        session.add(example_tenant)

        await session.flush()
        print(f"✓ Created tenant: {example_tenant.name} (ID: {example_tenant.tenant_id})")

        # Create user-tenant mappings
        print("Creating user-tenant mappings...")
        # Both admin and test user have access to example-tenant
        session.add(UserTenant(user_id=admin_user.id, tenant_id=example_tenant.id))
        session.add(UserTenant(user_id=test_user.id, tenant_id=example_tenant.id))

        print("✓ Created 2 user-tenant mappings")

        # Commit all changes
        await session.commit()
        print("✅ Central database seeded successfully!")

    # Seed tenant database with panel data
    await seed_tenant_data(example_tenant)

    print("\n" + "=" * 60)
    print("✅ ALL DATABASE SEEDING COMPLETED!")
    print("=" * 60)
    print("\nDevelopment Users (matching Keycloak):")
    print(f"  - {admin_user.email} (admin, username: adminuser, password: adminpass)")
    print(f"  - {test_user.email} (user, username: testuser, password: testpass)")
    print(f"\nDevelopment Tenant:")
    print(f"  - {example_tenant.name} (ID: {example_tenant.tenant_id})")
    print(f"    Both users have access to this tenant")
    print("\nTenant Database Tables Created:")
    print("  - metrics (300 records, for timeseries & KPI panels)")
    print("  - health_status (5 services)")
    print("  - logs (100 entries, for table panels)")


async def main() -> None:
    """Main entry point."""
    try:
        await seed_database()
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        await db_manager.close_all()


if __name__ == "__main__":
    asyncio.run(main())
