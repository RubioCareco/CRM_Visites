# nginx/Dockerfile

FROM nginx:alpine

# Copie la conf nginx (déjà existante)
COPY conf.d /etc/nginx/conf.d

# Script de démarrage qui attend que web:8000 soit dispo
COPY wait-for-web.sh /wait-for-web.sh
RUN chmod +x /wait-for-web.sh

# Point d’entrée : attend web:8000 puis démarre nginx
ENTRYPOINT ["/wait-for-web.sh", "web", "8000"]
