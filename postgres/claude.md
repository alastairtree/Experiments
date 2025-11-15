# PostgreSQL Setup Documentation

This document describes the configuration steps needed to set up PostgreSQL for local development.

## Quick Start (Automated Setup)

For the easiest setup, use the automated setup script that handles all configuration automatically:

```bash
./postgres/automated_setup.sh
```

This script will:
- Fix SSL certificate permissions
- Configure trust authentication for the postgres user
- Fix file ownership issues
- Start PostgreSQL
- Create the example database with sample data

**This is the recommended method for first-time setup.**

---

## Manual Setup (Step by Step)

If you prefer to set up manually or need to understand each step, follow these instructions:

### Minimal Setup (One Configuration Change)

#### 1. Configure Trust Authentication for postgres User

Edit `/etc/postgresql/16/main/pg_hba.conf` and change ONLY the postgres user line:

Change this line:
```
local   all             postgres                                peer
```

To:
```
local   all             postgres                                trust
```

**Why:** This allows connecting as the `postgres` database user from any local system user, while keeping peer authentication (the default) for all other users. This is the smallest configuration change needed.

#### 2. Reload PostgreSQL Configuration

```bash
pg_ctlcluster 16 main reload
```

Or if PostgreSQL isn't running, start it:
```bash
pg_ctlcluster 16 main start
```

## Verification

Check that PostgreSQL is running:

```bash
pg_lsclusters
```

Test connection as postgres user:
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

## Troubleshooting

### Issue: PostgreSQL fails to start with SSL certificate error

**Error message:**
```
FATAL:  private key file "/etc/ssl/private/ssl-cert-snakeoil.key" has group or world access
```

**Solution:**
```bash
chmod 600 /etc/ssl/private/ssl-cert-snakeoil.key
```

### Issue: PostgreSQL fails to start with "Permission denied" on pg_hba.conf

**Error message:**
```
could not open file "/etc/postgresql/16/main/pg_hba.conf": Permission denied
```

**Solution:**
Check that the file ownership matches other files in the directory:
```bash
ls -la /etc/postgresql/16/main/
chown claude:ubuntu /etc/postgresql/16/main/pg_hba.conf
```

Replace `claude:ubuntu` with the appropriate user:group for your system.

## Security Note

The "trust" authentication method is only appropriate for local development environments. For production systems, use "scram-sha-256" or other secure authentication methods with proper password management.
