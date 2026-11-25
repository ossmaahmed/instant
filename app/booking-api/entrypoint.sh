#!/bin/sh
# One-command startup: migrate, seed idempotent demo data, serve the API.
# Migrations are safe to repeat; the seed never duplicates and never creates
# accounts. Failures exit non-zero so they are visible in compose output.
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO:-true}" != "false" ]; then
  python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 2 --access-logfile - --error-logfile -
