#!/usr/bin/env bash
set -e

# Attendre la DB
echo "Waiting for DB ${DB_HOST}:${DB_PORT}..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done
echo "DB is up."

# Migrations + collectstatic
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Lancer Gunicorn (prod-like) sur 0.0.0.0:8000
exec gunicorn crm_visites.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120

