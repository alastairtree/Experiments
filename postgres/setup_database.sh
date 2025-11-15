#!/bin/bash

# PostgreSQL Database Setup Script
# This script creates a database called 'example' with a simple table and sample data

set -e  # Exit on error

echo "=== PostgreSQL Database Setup ==="
echo ""

# Database configuration
DB_NAME="example"
TABLE_NAME="users"
PORT="5432"

# Check if postgres user exists, if not create it
echo "Step 1: Ensuring postgres superuser exists..."
psql -U claude -d postgres -p $PORT -c "SELECT 1" >/dev/null 2>&1 || {
    echo "Creating postgres superuser role..."
    createuser -U claude -p $PORT -s postgres 2>/dev/null || echo "Superuser setup skipped"
}

# Drop database if it exists (for clean setup)
echo "Step 2: Dropping existing database if it exists..."
psql -U claude -d postgres -p $PORT -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

# Create database
echo "Step 3: Creating database '$DB_NAME'..."
psql -U claude -d postgres -p $PORT -c "CREATE DATABASE $DB_NAME;"

# Create table
echo "Step 4: Creating table '$TABLE_NAME'..."
psql -U claude -d $DB_NAME -p $PORT <<EOF
CREATE TABLE $TABLE_NAME (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

# Insert sample data
echo "Step 5: Inserting sample data..."
psql -U claude -d $DB_NAME -p $PORT <<EOF
INSERT INTO $TABLE_NAME (name, email) VALUES
    ('Alice Smith', 'alice@example.com'),
    ('Bob Johnson', 'bob@example.com'),
    ('Charlie Brown', 'charlie@example.com');
EOF

# Query and display the data
echo ""
echo "Step 6: Verifying data insertion..."
echo "=== Current data in $TABLE_NAME table ==="
psql -U claude -d $DB_NAME -p $PORT -c "SELECT * FROM $TABLE_NAME ORDER BY id;"

echo ""
echo "=== Database setup complete! ==="
echo "Database: $DB_NAME"
echo "Table: $TABLE_NAME"
echo "Port: $PORT"
echo ""
echo "To query the database manually, run:"
echo "  psql -U claude -d $DB_NAME -p $PORT"
