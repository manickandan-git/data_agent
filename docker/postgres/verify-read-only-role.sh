#!/bin/sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_MIGRATION_USER:?POSTGRES_MIGRATION_USER is required}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

export PGPASSWORD="$POSTGRES_APP_PASSWORD"

psql \
    --host=postgres \
    --username="$POSTGRES_APP_USER" \
    --dbname="$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="
        SELECT
            current_user,
            current_setting('default_transaction_read_only'),
            has_table_privilege(current_user, 'public.users', 'SELECT'),
            has_table_privilege(current_user, 'public.users', 'INSERT'),
            (SELECT count(*) >= 0 FROM public.users);
    "

table_owners="$(psql \
    --host=postgres \
    --username="$POSTGRES_APP_USER" \
    --dbname="$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="SELECT string_agg(DISTINCT tableowner, ',') FROM pg_tables WHERE schemaname = 'public';")"

if [ "$table_owners" != "$POSTGRES_MIGRATION_USER" ]; then
    echo "Ownership verification failed: public tables do not share the migration owner." >&2
    exit 1
fi

if psql \
    --host=postgres \
    --username="$POSTGRES_APP_USER" \
    --dbname="$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --command="BEGIN; CREATE TABLE public.data_agent_role_probe(id integer); ROLLBACK;"
then
    echo "Read-only verification failed: application DDL was accepted." >&2
    exit 1
fi

echo "Migration ownership and application read-only access are correctly enforced."
