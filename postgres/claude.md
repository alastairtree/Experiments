# PostgreSQL Setup Documentation

This document describes the configuration steps needed to set up PostgreSQL for local development.

## Quick Start (Automated Setup)

For the easiest setup, use the automated setup script:

```bash
./postgres/automated_setup.sh
```

This script will:
- Fix SSL certificate permissions (if needed)
- Create a database user matching your OS username
- Use peer authentication (no password, no config changes!)
- Start PostgreSQL
- Create the example database with sample data

**This is the recommended method - it requires ZERO configuration file changes!**

After setup, you can connect simply with:
```bash
psql -d example  # No -U flag needed!
```

---

## How It Works: Peer Authentication (Recommended)

PostgreSQL's default configuration uses "peer authentication" for local connections. This means:
- Your OS username (e.g., `claude`) automatically maps to a database username
- No password needed for local connections
- No configuration file edits required

**Setup steps:**
1. Create a database user matching your OS username: `CREATE USER claude WITH SUPERUSER;`
2. Connect without specifying a user: `psql -d postgres`
3. Done! PostgreSQL automatically detects you're the `claude` OS user

This is the **simplest and most secure** approach for local development.

---

## Manual Setup Options

If you prefer to set up manually or need to understand each step, choose one of these approaches:

### Option 1: Peer Authentication (Recommended - Zero Config Changes)

#### 1. Start PostgreSQL

```bash
# Fix SSL permissions if needed
chmod 600 /etc/ssl/private/ssl-cert-snakeoil.key

# Start PostgreSQL
pg_ctlcluster 16 main start
```

#### 2. Create Database User Matching Your OS Username

```bash
# Connect as postgres user (this still works with default peer auth)
su - postgres -c "psql -c 'CREATE USER claude WITH SUPERUSER;'"
```

Replace `claude` with your actual OS username.

#### 3. Connect and Use

```bash
# Connect without -U flag
psql -d postgres

# Create your database
CREATE DATABASE example;
```

**Why this is better:**
- No configuration file changes
- Uses PostgreSQL's default security settings
- Automatically maps OS user to database user
- No passwords to manage

---

### Option 2: Trust Authentication for postgres User (Alternative)

This approach allows any local user to connect as the `postgres` database user.

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

Once you have a database user set up (either using Option 1 or Option 2 above), you can create the example database:

```bash
./postgres/setup_database.sh
```

This script:
- Automatically uses your OS username as the database user (no -U flag needed!)
- Can be overridden with: `DB_USER=postgres ./postgres/setup_database.sh`
- Drops and recreates the "example" database
- Creates a "users" table with sample data
- Verifies the data was inserted correctly

## Manual Database Access

Connect to the example database:

```bash
# If using peer authentication (Option 1)
psql -d example

# If using trust authentication for postgres user (Option 2)
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
