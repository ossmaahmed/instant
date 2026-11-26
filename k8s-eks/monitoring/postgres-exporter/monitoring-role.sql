-- Read-only access for the postgres-exporter. NOT applied automatically.
-- Run it ONCE, as the PostgreSQL superuser, connected to the "booking" database,
-- and pass the new password as a psql variable (see README.md in this folder):
--   psql -v monitoring_pw="..." -d booking -f monitoring-role.sql
--
-- What the role can do:
--   * read PostgreSQL's own statistics (pg_monitor): connections, sizes, locks, transactions
--   * read three AGGREGATE views in schema "monitoring" (counts only)
-- What it cannot do:
--   * read the booking table itself, so it cannot see customer names or phone numbers
--   * write anything, create anything, or connect to the identity database
-- To remove it later: DROP SCHEMA monitoring CASCADE; DROP OWNED BY monitoring; DROP ROLE monitoring;

CREATE ROLE monitoring LOGIN PASSWORD :'monitoring_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5;
GRANT pg_monitor TO monitoring;
GRANT CONNECT ON DATABASE booking TO monitoring;
ALTER ROLE monitoring SET statement_timeout = '5s';
ALTER ROLE monitoring SET default_transaction_read_only = on;

CREATE SCHEMA monitoring;

-- Bookings by status and source (all time). Counts only, no personal data.
CREATE VIEW monitoring.booking_totals AS
SELECT status, source, count(*)::bigint AS bookings
FROM public.booking_booking
GROUP BY status, source;

-- Bookings created in the last 24 hours, by source (cancelled ones included).
CREATE VIEW monitoring.booking_created_24h AS
SELECT source, count(*)::bigint AS bookings
FROM public.booking_booking
WHERE created >= now() - interval '24 hours'
GROUP BY source;

-- Confirmed appointments still ahead: today (shop time) and the next 7 days.
CREATE VIEW monitoring.booking_upcoming AS
SELECT
    count(*) FILTER (WHERE (start AT TIME ZONE 'Africa/Cairo')::date = (now() AT TIME ZONE 'Africa/Cairo')::date
                       AND start >= now())::bigint AS today_remaining,
    count(*) FILTER (WHERE start >= now() AND start < now() + interval '7 days')::bigint AS next_7_days
FROM public.booking_booking
WHERE status = 'confirmed';

GRANT USAGE ON SCHEMA monitoring TO monitoring;
GRANT SELECT ON monitoring.booking_totals, monitoring.booking_created_24h, monitoring.booking_upcoming TO monitoring;
