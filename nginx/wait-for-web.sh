#!/bin/sh

host="$1"
port="$2"

echo "⏳ Attente de $host:$port..."

# Boucle jusqu'à ce que le port soit joignable
while ! nc -z "$host" "$port"; do
  sleep 2
  echo "🕒 $host:$port toujours pas dispo..."
done

echo "✅ $host:$port est maintenant disponible. Lancement de NGINX."
exec nginx -g 'daemon off;'
