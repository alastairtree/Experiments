# PostgreSQL Setup Documentation

This document describes the configuration steps needed to set up PostgreSQL for local development.

## Initial Setup Steps

### 1. Fix SSL Certificate Permissions

The PostgreSQL server requires strict permissions on the SSL key file:

```bash
chmod 0600 /etc/ssl/private/ssl-cert-snakeoil.key
```

**Why:** PostgreSQL won't start if the private key file has group or world access permissions.

### 2. Configure Authentication Method

Modified `/etc/postgresql/16/main/pg_hba.conf` to allow local connections without password:

Changed from:
```
local   all             postgres                                peer
local   all             all                                     peer
```

To:
```
local   all             postgres                                trust
local   all             all                                     trust
```

**Why:** "peer" authentication requires the system username to match the PostgreSQL username. Using "trust" allows connections from any local user without authentication (safe for local development).

### 3. Fix pg_hba.conf File Permissions

```bash
chmod 644 /etc/postgresql/16/main/pg_hba.conf
chown claude:ubuntu /etc/postgresql/16/main/pg_hba.conf
```

**Why:** PostgreSQL needs to read the configuration file, and the file ownership/permissions need to be correct.

### 4. Create PostgreSQL User

Created a superuser role for the "claude" system user:

```bash
psql -U postgres -d postgres -p 5432 -c "CREATE USER claude WITH SUPERUSER CREATEDB CREATEROLE LOGIN;"
```

**Why:** This allows the "claude" system user to connect to PostgreSQL and create databases.

### 5. Start PostgreSQL Service

```bash
pg_ctlcluster 16 main start
```

To reload configuration without restart:
```bash
pg_ctlcluster 16 main reload
```

## Verification

Check that PostgreSQL is running:

```bash
pg_lsclusters
```

Expected output:
```
Ver Cluster Port Status Owner  Data directory              Log file
16  main    5432 online claude /var/lib/postgresql/16/main /var/log/postgresql/postgresql-16-main.log
```

Test connection:
```bash
psql -U claude -d postgres -p 5432 -c "SELECT version();"
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
psql -U claude -d example -p 5432
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
