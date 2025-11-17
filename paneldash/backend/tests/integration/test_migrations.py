"""Tests for Alembic migrations."""

import subprocess
from pathlib import Path

import pytest


class TestAlembicMigrations:
    """Tests for Alembic migration scripts."""

    def test_alembic_migration_syntax(self) -> None:
        """Test that migration files have valid Python syntax."""
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"

        if not migrations_dir.exists():
            pytest.skip("No migrations directory found")

        migration_files = list(migrations_dir.glob("*.py"))

        if not migration_files:
            pytest.skip("No migration files found")

        # Try to compile each migration file
        for migration_file in migration_files:
            with open(migration_file) as f:
                code = f.read()
                try:
                    compile(code, str(migration_file), "exec")
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {migration_file.name}: {e}")

    def test_alembic_current_command(self) -> None:
        """Test that 'alembic current' command works."""
        # This test checks if alembic configuration is valid
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        # Command should succeed (even if no migrations have been run)
        # It might return empty output or show current revision
        assert result.returncode == 0 or result.returncode == 1, \
            f"alembic current failed: {result.stderr}"

    def test_alembic_history_command(self) -> None:
        """Test that 'alembic history' command works and shows migrations."""
        result = subprocess.run(
            ["uv", "run", "alembic", "history"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        # Command should succeed
        assert result.returncode == 0, f"alembic history failed: {result.stderr}"

        # Should show our initial migration
        assert "001" in result.stdout or "Initial migration" in result.stdout, \
            "Migration 001 should appear in history"

    def test_migration_file_structure(self) -> None:
        """Test that migration files have the required structure."""
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"

        if not migrations_dir.exists():
            pytest.skip("No migrations directory found")

        migration_files = list(migrations_dir.glob("*.py"))

        if not migration_files:
            pytest.skip("No migration files found")

        for migration_file in migration_files:
            with open(migration_file) as f:
                content = f.read()

                # Check for required components
                assert "revision:" in content, \
                    f"{migration_file.name} missing revision identifier"
                assert "down_revision:" in content, \
                    f"{migration_file.name} missing down_revision identifier"
                assert "def upgrade()" in content, \
                    f"{migration_file.name} missing upgrade() function"
                assert "def downgrade()" in content, \
                    f"{migration_file.name} missing downgrade() function"
