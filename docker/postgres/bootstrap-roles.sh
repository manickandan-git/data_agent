#!/bin/sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_MIGRATION_USER:?POSTGRES_MIGRATION_USER is required}"
: "${POSTGRES_MIGRATION_PASSWORD:?POSTGRES_MIGRATION_PASSWORD is required}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

if [ "$POSTGRES_USER" = "$POSTGRES_MIGRATION_USER" ] || \
   [ "$POSTGRES_USER" = "$POSTGRES_APP_USER" ] || \
   [ "$POSTGRES_MIGRATION_USER" = "$POSTGRES_APP_USER" ]; then
    echo "Database administrator, migration, and application roles must be distinct." >&2
    exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"

psql \
    --host=postgres \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --set=migration_role="$POSTGRES_MIGRATION_USER" \
    --set=migration_password="$POSTGRES_MIGRATION_PASSWORD" \
    --set=application_role="$POSTGRES_APP_USER" \
    --set=application_password="$POSTGRES_APP_PASSWORD" \
    --set=database_name="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I', :'migration_role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'migration_role')
\gexec

SELECT format('CREATE ROLE %I', :'application_role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'application_role')
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
    :'migration_role',
    :'migration_password'
)
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
    :'application_role',
    :'application_password'
)
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'database_name', :'migration_role')
\gexec
SELECT format('REVOKE ALL PRIVILEGES ON DATABASE %I FROM %I', :'database_name', :'application_role')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'database_name', :'application_role')
\gexec
SELECT format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', :'database_name')
\gexec

SELECT format('REVOKE %I FROM %I', granted_role.rolname, :'application_role')
FROM pg_auth_members membership
JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
JOIN pg_roles member_role ON member_role.oid = membership.member
WHERE member_role.rolname = :'application_role'
\gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('ALTER SCHEMA public OWNER TO %I', :'migration_role')
\gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'migration_role')
\gexec

SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'migration_role')
FROM pg_tables
WHERE schemaname = 'public'
\gexec

SELECT format('ALTER SEQUENCE %I.%I OWNER TO %I', sequence_schema, sequence_name, :'migration_role')
FROM information_schema.sequences
WHERE sequence_schema = 'public'
\gexec

SELECT format('REVOKE ALL ON SCHEMA public FROM %I', :'application_role')
\gexec
SELECT format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM %I', :'application_role')
\gexec
SELECT format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM %I', :'application_role')
\gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'application_role')
\gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA public TO %I', :'application_role')
\gexec
SELECT format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'application_role')
\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON TABLES TO %I',
    :'migration_role',
    :'application_role'
)
\gexec
SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON SEQUENCES TO %I',
    :'migration_role',
    :'application_role'
)
\gexec

SELECT format(
    'ALTER ROLE %I IN DATABASE %I SET default_transaction_read_only = on',
    :'application_role',
    :'database_name'
)
\gexec
SQL

echo "Database roles and least-privilege grants are configured."
