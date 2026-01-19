#!/usr/bin/env bash
set -e
echo "🛠️  Environnement détecté : ${ENV:-unknown}"

# Attendre la DB
echo "Waiting for DB ${DB_HOST:-localhost}:${DB_PORT:-3306}..."
TRIES=0
until nc -z "${DB_HOST:-localhost}" "${DB_PORT:-3306}"; do
  TRIES=$((TRIES+1))
  if [ "$TRIES" -ge 60 ]; then
    echo "❌ DB not reachable after 60s"
    exit 1
  fi
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
