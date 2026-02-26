# CRM Visites

Application Django de gestion commerciale pour planifier, optimiser et suivre les rendez-vous clients, les objectifs annuels de visite et la satisfaction B2B.

## Sommaire
- Vue d'ensemble
- Fonctionnalités
- Rôles
- Stack technique
- Arborescence
- Installation locale
- Configuration (.env)
- Commandes de gestion
- Tests
- Déploiement Docker
- Sécurité
- Licence

## Vue d'ensemble
Le projet couvre 3 axes métier principaux:
- pilotage des rendez-vous commerciaux (création, validation, annulation, historique)
- planification automatique et optimisation géographique des tournées
- suivi de performance (objectifs annuels + satisfaction B2B)

## Fonctionnalités

### 1) Authentification et session
- Connexion/déconnexion via entité métier `Commercial`
- Réinitialisation de mot de passe par token signé (`new-password`)
- Timeout de session + endpoint de prolongation (`/extend-session/`)
- Rate limiting sur les endpoints sensibles (login, reset, update statut, etc.)

### 2) Gestion des clients
- Création/édition de clients (`FrontClient`) + adresses (`Adresse`)
- Validation SIRET (Luhn) + normalisation
- Enrichissement INSEE via API (`/api/insee/siret/<siret>/`)
- Recherche client (autocomplete + table)
- Import clients Excel/CSV

### 3) Gestion des rendez-vous
- Création de RDV (`Rendezvous`)
- Statuts principaux: `a_venir`, `valide`, `annule`, `gele`
- Contrainte anti-doublon DB: `(commercial, client, date_rdv, heure_rdv)`
- Commentaires RDV (`CommentaireRdv`) avec pin/unpin
- Historique commercial et responsable

### 4) Planification automatique
- Service `ensure_visits_next_4_weeks` (horizon J+28)
- Jours ouvrés uniquement (week-ends + fériés)
- Prise en compte objectifs annuels et absences commerciaux
- Idempotence + quotas journaliers + filtres géographiques

### 5) Optimisation géographique
- Géocodage Nominatim (fallbacks)
- Optimisation d'ordre: nearest-neighbor + 2-opt
- Coût routier: Google Distance Matrix/Directions si clé API, sinon Haversine
- Carte tournée et APIs associées

### 6) Satisfaction B2B
- Formulaire de satisfaction lié au RDV
- Génération PDF (stocké en base64)
- Calcul score hybride + agrégations dashboard
- Export Excel des satisfactions

### 7) Pilotage et reporting
- Dashboard commercial (`dashboard_test`)
- Dashboard responsable (`dashboard_responsable`)
- Journal d'activité (`ActivityLog`)
- Suivi des objectifs annuels (`ClientVisitStats`)

## Rôles
- `commercial`: accès à son périmètre (clients, RDV, tournée, objectifs)
- `responsable`: supervision multi-commerciaux
- `admin`: mêmes capacités métier qu'un responsable + administration élargie

## Stack technique
- Python 3.12
- Django 5.2
- MySQL (`mysqlclient`)
- WhiteNoise (statiques côté app)
- Nginx (reverse proxy en prod)
- Gunicorn
- Pandas/OpenPyXL (imports/exports)
- Geopy + Requests (géocodage/routing)
- xhtml2pdf/ReportLab (PDF)

## Arborescence
```text
crm_visites/
├─ crm_visites/                 # settings, urls, asgi, wsgi
├─ front/                       # app Django principale
│  ├─ management/commands/      # commandes métier/exploitation
│  ├─ migrations/
│  ├─ templates/front/
│  ├─ static/front/
│  ├─ models.py
│  ├─ views.py
│  ├─ services.py
│  ├─ utils.py
│  ├─ middleware.py
│  └─ signals.py
├─ nginx/conf.d/app.conf
├─ docker-compose.yml
├─ docker-compose.prod.yml
├─ Dockerfile
├─ entrypoint.sh
├─ requirements.txt
└─ README.md
```

## Installation locale

### Pré-requis
- Python 3.11+
- MySQL 8 (ou service MySQL via Docker)
- pip

### Étapes
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Initialisation
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Application: `http://127.0.0.1:8000`

## Configuration (.env)
Créer un fichier `.env` à la racine (base: `.env.example`).

Variables importantes:

```env
# Django
DJANGO_SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000
SITE_BASE_URL=http://127.0.0.1:8000

# Base de données
DB_NAME=crm_visites
DB_USER=appuser
DB_PASSWORD=apppass
DB_HOST=db
DB_PORT=3306

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@rubio.fr

# Planification auto
GENERATION_AUTO_ENABLED=True
GENERATION_AUTO_DRY_RUN=False

# Géographie
MAX_RADIUS_KM=40
MAX_DAILY_DISTANCE_KM=220
CLUSTER_RADIUS_KM=10
SAME_DAY_SPREAD_KM=15
ROUTING_AVG_SPEED_KMH=50

# Google routing (optionnel)
GOOGLE_MAPS_API_KEY=

# Jours fériés
HOLIDAYS_COUNTRY=FR
HOLIDAYS_YEARS=2025,2026
PUBLIC_HOLIDAYS=2025-01-01,2025-05-01,2025-12-25
```

En production, utiliser `.env.prod` (voir `.env.prod.example`).

## Commandes de gestion

### Planification / capacité
```bash
python manage.py ensure_next_4_weeks
python manage.py generer_rdv_4semaines --weeks 4
python manage.py generer_rdv_mensuel --month 2026-03
python manage.py cap_daily_quota --daily-quota 6 --days 35
python manage.py capacity --year 2026 --month 3 --daily-quota 6
```

### Géocodage / cartographie
```bash
python manage.py geocode_addresses
python manage.py geocode_sample
python manage.py show_route --commercial "Commercial 2" --date 2026-03-15
```

### Données / maintenance
```bash
python manage.py migrate_import_clients
python manage.py map_commerciaux
python manage.py init_visit_stats --annee 2026
python manage.py generate_missing_objectives
python manage.py update_client_objectifs
python manage.py fix_addresses
python manage.py fill_rdv_rs_nom
python manage.py nettoyer_rdv_anciens --days 1
python manage.py update_scores_hybrides
python manage.py fix_satisfaction_scores --dry-run
python manage.py purge_demo_data --dry-run
```

### Sécurité / groupes
```bash
python manage.py create_responsable_group --emails responsable@exemple.com
python manage.py test_session_timeout
python manage.py test_signals
```

## Tests
```bash
pytest -q
# ou
pytest -vv
```

Fichiers principaux:
- `front/tests.py`
- `front/tests_security_phase1.py`

## Déploiement Docker

### Développement
```bash
docker compose up -d --build
```

### Production (web + nginx)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod ps
```

Healthcheck:
- app Django: `/healthz`

## Sécurité
- CSRF activé
- Headers de sécurité via middleware (`SecurityHeadersMiddleware`)
- Session timeout + avertissement
- Cookies sécurisés renforcés en `ENV=prod`
- Rate limiting sur endpoints sensibles
- Contrôle d'accès par rôle et périmètre commercial

## Licence
Projet sous licence MIT. Voir `LICENSE`.
