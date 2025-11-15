#!/bin/bash

# PostgreSQL Database Setup Script
# This script creates a database called 'example' with a simple table and sample data
# By default uses the current OS user (works with peer authentication)
# Set DB_USER environment variable to override (e.g., DB_USER=postgres ./setup_database.sh)

set -e  # Exit on error

echo "=== PostgreSQL Database Setup ==="
echo ""

# Database configuration
DB_NAME="example"
TABLE_NAME="users"
DB_USER="${DB_USER:-$(whoami)}"  # Default to current user, can be overridden

echo "Connecting as database user: $DB_USER"
echo ""

# Drop database if it exists (for clean setup)
echo "Step 1: Dropping existing database if it exists..."
psql -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

# Create database
echo "Step 2: Creating database '$DB_NAME'..."
psql -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;"

# Create table
echo "Step 3: Creating table '$TABLE_NAME'..."
psql -U $DB_USER -d $DB_NAME <<EOF
CREATE TABLE $TABLE_NAME (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

# Insert sample data
echo "Step 4: Inserting sample data..."
psql -U $DB_USER -d $DB_NAME <<EOF
INSERT INTO $TABLE_NAME (name, email) VALUES
    ('Alice Smith', 'alice@example.com'),
    ('Bob Johnson', 'bob@example.com'),
    ('Charlie Brown', 'charlie@example.com');
EOF

# Query and display the data
echo ""
echo "Step 5: Verifying data insertion..."
echo "=== Current data in $TABLE_NAME table ==="
psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM $TABLE_NAME ORDER BY id;"

echo ""
echo "=== Database setup complete! ==="
echo "Database: $DB_NAME"
echo "Table: $TABLE_NAME"
echo ""
echo "To query the database manually, run:"
echo "  psql -U $DB_USER -d $DB_NAME"
