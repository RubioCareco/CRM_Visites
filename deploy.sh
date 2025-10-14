#!/bin/bash

echo "🧱 [1/3] Arrêt et nettoyage des conteneurs..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

echo "🚀 [2/3] Reconstruction et démarrage des services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

echo "✅ [3/3] Déploiement terminé. App disponible sur : http://localhost"
