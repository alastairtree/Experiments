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

        # Create test users
        print("Creating users...")
        admin_user = User(
            keycloak_id="admin-keycloak-id",
            email="admin@paneldash.local",
            full_name="Admin User",
            is_admin=True,
        )
        session.add(admin_user)

        user1 = User(
            keycloak_id="user1-keycloak-id",
            email="user1@paneldash.local",
            full_name="Test User 1",
            is_admin=False,
        )
        session.add(user1)

        user2 = User(
            keycloak_id="user2-keycloak-id",
            email="user2@paneldash.local",
            full_name="Test User 2",
            is_admin=False,
        )
        session.add(user2)

        await session.flush()  # Get IDs without committing
        print(f"✓ Created 3 users (admin: {admin_user.email})")

        # Create test tenants
        print("Creating tenants...")
        tenant_alpha = Tenant(
            tenant_id="tenant-alpha",
            name="Alpha Corporation",
            database_name="tenant_alpha",
            database_host=settings.central_db_host,
            database_port=settings.central_db_port,
            database_user=settings.central_db_user,
            database_password=settings.central_db_password,
            is_active=True,
        )
        session.add(tenant_alpha)

        tenant_beta = Tenant(
            tenant_id="tenant-beta",
            name="Beta Industries",
            database_name="tenant_beta",
            database_host=settings.central_db_host,
            database_port=settings.central_db_port,
            database_user=settings.central_db_user,
            database_password=settings.central_db_password,
            is_active=True,
        )
        session.add(tenant_beta)

        await session.flush()
        print(f"✓ Created 2 tenants ({tenant_alpha.name}, {tenant_beta.name})")

        # Create user-tenant mappings
        print("Creating user-tenant mappings...")
        # Admin has access to all tenants
        session.add(UserTenant(user_id=admin_user.id, tenant_id=tenant_alpha.id))
        session.add(UserTenant(user_id=admin_user.id, tenant_id=tenant_beta.id))

        # User1 has access to tenant-alpha
        session.add(UserTenant(user_id=user1.id, tenant_id=tenant_alpha.id))

        # User2 has access to tenant-beta
        session.add(UserTenant(user_id=user2.id, tenant_id=tenant_beta.id))

        print("✓ Created 4 user-tenant mappings")

        # Commit all changes
        await session.commit()
        print("✅ Database seeded successfully!")
        print("\nDevelopment Users:")
        print(f"  - {admin_user.email} (admin, access to all tenants)")
        print(f"  - {user1.email} (access to {tenant_alpha.name})")
        print(f"  - {user2.email} (access to {tenant_beta.name})")


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
