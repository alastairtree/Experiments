#!/bin/bash

# Automated PostgreSQL Setup Script
# This script handles all configuration and setup steps automatically

set -e  # Exit on error

echo "=== Automated PostgreSQL Setup ==="
echo ""

# Check if PostgreSQL is installed
if ! command -v pg_lsclusters &> /dev/null; then
    echo "ERROR: PostgreSQL is not installed"
    exit 1
fi

echo "Step 1: Fixing SSL certificate permissions..."
if [ -f /etc/ssl/private/ssl-cert-snakeoil.key ]; then
    chmod 600 /etc/ssl/private/ssl-cert-snakeoil.key
    echo "  ✓ SSL certificate permissions fixed"
else
    echo "  ! SSL certificate not found (this is OK if SSL is not configured)"
fi

echo ""
echo "Step 2: Configuring PostgreSQL authentication..."
PG_HBA_CONF="/etc/postgresql/16/main/pg_hba.conf"

if [ ! -f "$PG_HBA_CONF" ]; then
    echo "ERROR: pg_hba.conf not found at $PG_HBA_CONF"
    exit 1
fi

# Backup the original file if not already backed up
if [ ! -f "$PG_HBA_CONF.backup" ]; then
    cp "$PG_HBA_CONF" "$PG_HBA_CONF.backup"
    echo "  ✓ Created backup: $PG_HBA_CONF.backup"
fi

# Update the postgres user authentication to trust
sed -i 's/^local\s*all\s*postgres\s*peer$/local   all             postgres                                trust/' "$PG_HBA_CONF"
echo "  ✓ Configured trust authentication for postgres user"

# Fix ownership to match other config files
OWNER=$(stat -c '%U:%G' /etc/postgresql/16/main/postgresql.conf)
chown "$OWNER" "$PG_HBA_CONF"
echo "  ✓ Fixed pg_hba.conf ownership to $OWNER"

echo ""
echo "Step 3: Starting PostgreSQL..."
# Check if PostgreSQL is already running
if pg_lsclusters | grep -q "16.*main.*online"; then
    echo "  PostgreSQL is already running, reloading configuration..."
    pg_ctlcluster 16 main reload
else
    echo "  Starting PostgreSQL..."
    pg_ctlcluster 16 main start
fi
echo "  ✓ PostgreSQL is running"

echo ""
echo "Step 4: Verifying PostgreSQL connection..."
if psql -U postgres -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    echo "  ✓ Successfully connected to PostgreSQL"
else
    echo "ERROR: Cannot connect to PostgreSQL"
    exit 1
fi

echo ""
echo "Step 5: Running database setup script..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/setup_database.sh"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "PostgreSQL is configured and the example database is ready."
echo ""
echo "Connection details:"
echo "  Database: example"
echo "  User: postgres"
echo "  Command: psql -U postgres -d example"
echo ""
