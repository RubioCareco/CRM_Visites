#!/usr/bin/env bash
set -e
echo "🛠️  Environnement détecté : ${ENV:-unknown}"

# Attendre la DB
echo "Waiting for DB ${DB_HOST}:${DB_PORT}..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done
echo "DB is up."

# Pas de chown/chmod ici
mkdir -p /app/staticfiles

# Migrations + collectstatic
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Lancer Gunicorn
exec gunicorn crm_visites.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
