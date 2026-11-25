#!/bin/sh
# Runs automatically once, when the postgres_data volume is empty.
# Creates one database and one least-privilege role per service. Each role
# owns its own database and cannot connect to the other one.
set -eu

# The passwords come from .env and may contain any characters. They are passed
# to psql as variables and expanded with :'name', which quotes them as SQL
# literals, so quotes, backslashes and dollar signs are all safe. Reject empty
# values before touching the database instead of writing a broken role.
for v in BOOKING_DB_PASSWORD IDENTITY_DB_PASSWORD; do
    eval "val=\${$v:-}"
    if [ -z "$val" ]; then
        echo "db init: $v is empty; set it in .env before first start" >&2
        exit 1
    fi
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${POSTGRES_DB:-postgres}" \
    -v booking_pw="$BOOKING_DB_PASSWORD" \
    -v identity_pw="$IDENTITY_DB_PASSWORD" <<-'SQL'
    CREATE ROLE booking LOGIN PASSWORD :'booking_pw';
    CREATE DATABASE booking OWNER booking;
    REVOKE CONNECT ON DATABASE booking FROM PUBLIC;
    CREATE ROLE identity LOGIN PASSWORD :'identity_pw';
    CREATE DATABASE identity OWNER identity;
    REVOKE CONNECT ON DATABASE identity FROM PUBLIC;
SQL
