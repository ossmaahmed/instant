#!/bin/sh
# The web service owns no business data; migrate only creates its private
# session table (SQLite file inside this container).
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -
