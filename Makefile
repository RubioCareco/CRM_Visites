.PHONY: up down logs web-logs db-logs migrate collectstatic shell createsuperuser backup restore

up: ## Démarrer les services
	docker compose up -d

down: ## Stop + remove
	docker compose down

logs: ## Logs de tous les services
	docker compose logs -f

web-logs:
	docker compose logs -f web

db-logs:
	docker compose logs -f db

migrate: ## Appliquer les migrations
	docker compose exec web python manage.py migrate --noinput

collectstatic: ## Collecte des fichiers statiques
	docker compose exec web python manage.py collectstatic --noinput

shell: ## Shell Django
	docker compose exec web python manage.py shell

createsuperuser: ## Créer un superuser
	docker compose exec web python manage.py createsuperuser

backup: ## Dump SQL daté (hors repo)
	mkdir -p backups
	docker compose exec -T db mysqldump -uappuser -papppass \
		--no-tablespaces --single-transaction --quick --lock-tables=false \
		--routines --events --triggers --set-gtid-purged=OFF --column-statistics=0 \
		crm_visites > backups/backup_$$(date +%F).sql

restore: ## Restaurer le dernier dump backups/*.sql 
	docker compose exec -T db sh -lc 'ls -1t /tmp/restore.sql 2>/dev/null || true'
	# Copie le plus récent dump dans le conteneur
	docker compose exec -T db sh -lc "rm -f /tmp/restore.sql"
	cat $$(ls -1t backups/*.sql | head -n1) | docker compose exec -T db sh -lc "cat >/tmp/restore.sql"
	# Drop + recreate + import
	docker compose exec -T db sh -lc 'mysql -uroot -p"$$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS crm_visites; CREATE DATABASE crm_visites CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
	docker compose exec -T db sh -lc 'mysql -uappuser -papppass --default-character-set=utf8mb4 crm_visites < /tmp/restore.sql'
