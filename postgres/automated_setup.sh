#!/bin/bash

# Automated PostgreSQL Setup Script
# This script handles all setup steps automatically using peer authentication
# No pg_hba.conf changes needed!

set -e  # Exit on error

echo "=== Automated PostgreSQL Setup ==="
echo ""

# Get the current user (the one who will use the database)
# If running as root, check for SUDO_USER or TARGET_USER env variable
# Otherwise, use the PostgreSQL cluster owner as the target user
if [ "$(whoami)" = "root" ]; then
    if [ -n "$SUDO_USER" ]; then
        CURRENT_USER="$SUDO_USER"
    elif [ -n "$TARGET_USER" ]; then
        CURRENT_USER="$TARGET_USER"
    else
        # Get the PostgreSQL cluster owner as fallback
        CURRENT_USER=$(pg_lsclusters -h | awk '{print $5}' | head -1)
    fi
else
    CURRENT_USER=$(whoami)
fi

echo "Setting up PostgreSQL for user: $CURRENT_USER"
echo ""

# Check if PostgreSQL is installed
if ! command -v pg_lsclusters &> /dev/null; then
    echo "ERROR: PostgreSQL is not installed"
    exit 1
fi

echo "Step 1: Fixing SSL certificate permissions (if needed)..."
if [ -f /etc/ssl/private/ssl-cert-snakeoil.key ]; then
    chmod 600 /etc/ssl/private/ssl-cert-snakeoil.key
    echo "  ✓ SSL certificate permissions fixed"
else
    echo "  ! SSL certificate not found (this is OK if SSL is not configured)"
fi

echo ""
echo "Step 2: Starting PostgreSQL..."
# Check if PostgreSQL is already running
if pg_lsclusters | grep -q "16.*main.*online"; then
    echo "  ✓ PostgreSQL is already running"
else
    echo "  Starting PostgreSQL..."
    pg_ctlcluster 16 main start
    echo "  ✓ PostgreSQL started"
fi

echo ""
echo "Step 3: Creating database user '$CURRENT_USER' (if it doesn't exist)..."
# Check if user exists, create if not
if su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$CURRENT_USER'\"" | grep -q 1; then
    echo "  ✓ User '$CURRENT_USER' already exists"
else
    su - postgres -c "psql -c \"CREATE USER $CURRENT_USER WITH SUPERUSER;\""
    echo "  ✓ Created database user '$CURRENT_USER' with superuser privileges"
fi

echo ""
echo "Step 4: Verifying connection as '$CURRENT_USER'..."
if su - "$CURRENT_USER" -c "psql -d postgres -c 'SELECT version();'" > /dev/null 2>&1; then
    echo "  ✓ Successfully connected as '$CURRENT_USER' (using peer authentication)"
else
    echo "ERROR: Cannot connect as '$CURRENT_USER'"
    exit 1
fi

echo ""
echo "Step 5: Running database setup script..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
su - "$CURRENT_USER" -c "cd '$SCRIPT_DIR' && ./setup_database.sh"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "PostgreSQL is ready with zero configuration changes!"
echo ""
echo "Key points:"
echo "  • Database user '$CURRENT_USER' created (matches your OS username)"
echo "  • Peer authentication enabled by default (no password needed)"
echo "  • No pg_hba.conf modifications required"
echo ""
echo "Connection details:"
echo "  Database: example"
echo "  User: $CURRENT_USER"
echo "  Command: psql -d example"
echo "  (No -U flag needed - peer auth auto-detects your username!)"
echo ""
