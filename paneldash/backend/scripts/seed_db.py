"""Seed the database with development data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.config import settings
from app.database import db_manager
from app.models.central import Tenant, User, UserTenant


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
            database_name="tenant_example",
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
        print("✅ Database seeded successfully!")
        print("\nDevelopment Users (matching Keycloak):")
        print(f"  - {admin_user.email} (admin, username: adminuser, password: adminpass)")
        print(f"  - {test_user.email} (user, username: testuser, password: testpass)")
        print(f"\nDevelopment Tenant:")
        print(f"  - {example_tenant.name} (ID: {example_tenant.tenant_id})")
        print(f"    Both users have access to this tenant")


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
