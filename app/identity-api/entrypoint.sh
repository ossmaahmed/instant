#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn -c gunicorn.conf.py config.wsgi:application --bind 0.0.0.0:8002 --workers 2 --access-logfile - --error-logfile -
