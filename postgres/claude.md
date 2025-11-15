# PostgreSQL Setup Documentation

This document describes the minimal configuration steps needed to set up PostgreSQL for local development.

## Minimal Setup Steps

### 1. Configure Authentication for postgres User

Edit `/etc/postgresql/16/main/pg_hba.conf` and change the postgres user authentication method:

Change this line:
```
local   all             postgres                                peer
```

To:
```
local   all             postgres                                trust
```

**Why:** This allows any local user to connect as the postgres database user without password authentication. This is the only configuration change needed.

### 2. Start PostgreSQL Service

```bash
pg_ctlcluster 16 main start
```

## Verification

Check that PostgreSQL is running:

```bash
pg_lsclusters
```

Test connection:
```bash
psql -U postgres -d postgres -c "SELECT version();"
```

## Using the Setup Script

Once the initial setup is complete, the database can be created using:

```bash
./postgres/setup_database.sh
```

This script will:
- Drop and recreate the "example" database
- Create a "users" table with sample data
- Verify the data was inserted correctly

## Manual Database Access

Connect to the example database:

```bash
psql -U postgres -d example
```

Common psql commands:
- `\l` - list all databases
- `\dt` - list tables in current database
- `\d table_name` - describe table structure
- `\q` - quit psql

## Environment Details

- **PostgreSQL Version:** 16.10
- **Port:** 5432
- **Data Directory:** /var/lib/postgresql/16/main
- **Config Directory:** /etc/postgresql/16/main/
- **Log File:** /var/log/postgresql/postgresql-16-main.log

## Security Note

The "trust" authentication method is only appropriate for local development environments. For production systems, use "scram-sha-256" or other secure authentication methods with proper password management.
