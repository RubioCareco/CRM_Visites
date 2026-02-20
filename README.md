# 🏢 CRM Visites – Application Django de planification commerciale

Solution CRM pour planifier, optimiser et suivre les rendez‑vous commerciaux, les objectifs annuels et la satisfaction B2B. Configuration par variables d’environnement, planification automatique sur 4 semaines et optimisation d’itinéraires.

## 📋 Sommaire

- Fonctionnalités clés
- Installation rapide
- Configuration (.env)
- Lancer en local
- Génération auto J+28 (au login)
- Optimisation d’itinéraires (Google/Haversine)
- Commandes utiles
- Tests
- Déploiement Docker (web + nginx)
- Bonnes pratiques prod

## ✨ Fonctionnalités clés

- Rendez‑vous
  - Statuts: à venir, validé, annulé, gelé
  - Créneaux matin uniquement: 09:00 → 12:00 (toutes les 30 min). Aucun slot après 12:30
  - Jours ouvrés uniquement (week‑ends exclus) + jours fériés FR (lib `holidays` ou liste manuelle)
  - Plafond: 6 RDV/jour/commercial
  - Idempotence: aucune duplication à l’exécution

- Planification automatique (J → J+28)
  - Déclenchée automatiquement au premier login de la journée (verrou cache 1×/jour)
  - Respect des objectifs annuels par client (A=10, B=5, C=1, vide=1) et des visites déjà validées
  - Prend en compte les absences des commerciaux (aucune création)= statut gelé. 
  - Sélection géographique: filtre par rayon autour du point de départ, clustering par proximité, puis sélection des RDV (les 6 plus proches les uns des autres en partant du départ)

- Optimisation d’itinéraires
  - Ordre optimisé via Nearest Neighbor + amélioration 2‑opt
  - Coût routier: Google Distance Matrix/Directions prioritaire. Fallback Haversine
  - Estimation du temps total: Google si possible, sinon Haversine à vitesse moyenne (50 km/h)

- Géocodage
  - Nominatim (OpenStreetMap) avec logique de fallback simple

- Sécurité et configuration
  - `django-environ` pour toutes les variables sensibles
  - Cookies sécurisés / redirection HTTPS si `DEBUG=False`
  - Statiques servis via WhiteNoise en web et via nginx en prod

## 📚 Bibliothèques utilisées et rôles

- Framework et serveur
  - Django: framework web principal (ORM, vues, templates, admin)
  - gunicorn: serveur WSGI (prod)
  - whitenoise: service des fichiers statiques depuis l’app (prod)

- Base de données
  - mysqlclient: pilote MySQL pour Django

- Géolocalisation et distances
  - geopy, geographiclib: géocodage Nominatim et calculs géographiques

- PDF / rendu
  - xhtml2pdf (pisa): moteur HTML→PDF utilisé par l’app (ex. export B2B)
  - reportlab: dépendance de xhtml2pdf pour le rendu PDF
  - html5lib, webencodings: parsing/encodages HTML requis par xhtml2pdf

- Données / Excel / Numérique
  - pandas, numpy: traitement de données
  - openpyxl, et_xmlfile: import/export Excel

- Texte / NLP
  - textblob, nltk, regex: analyse de texte

- Réseau / HTTP
  - requests, urllib3, chardet, charset-normalizer, idna, certifi: appels HTTP robustes (ex. Google APIs)

- Sécurité / crypto (documents signés)
  - cryptography, cffi, pycparser, oscrypto, asn1crypto, pyHanko, pyhanko-certvalidator: primitives crypto, signatures et validation

- Internationalisation / fuseaux
  - pytz, tzdata, tzlocal, python-dateutil: gestion des fuseaux et dates

- Configuration / utilitaires
  - django-environ: lecture des variables d’environnement (.env)
  - PyYAML: lecture/écriture YAML
  - click, colorama, tqdm, six, sqlparse, pillow, lxml, Brotli, uritools, arabic-reshaper, python-bidi, pypdf, joblib: utilitaires divers (CLI, couleurs, barre de progression, compat, parsing SQL, images, XML/HTML, compression, URLs, rendu texte RTL, PDF, parallélisme léger)

## 🚀 Installation rapide

```bash
python -m venv venv                             -> (Création d'un environnement virtuel en python local)
venv\Scripts\activate  # Windows                -> (Activation de l'environnement virtuel)
# source venv/bin/activate  # Linux/Mac
python -m pip install --upgrade pip             -> (Met à jour PIP, le gestionnaire de paquets Python, à la dernière version dans l'environnement virtuel)
pip install -r requirements.txt                 -> (Install toute les dépendances listées dans requirement.txt, qui sont necessaire pour faire fonctionner le projet)
```

## ⚙️ Configuration (.env)

Créez `.env` à la racine (voir aussi `.env.example`):

```env
# Django
DJANGO_SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000

# Base de données
DB_NAME=crm_visites
DB_USER=appuser
DB_PASSWORD=apppass
DB_HOST=db
DB_PORT=3306

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@rubio.fr
SITE_BASE_URL=http://127.0.0.1:8000

# Jours fériés (lib holidays prioritaire, fallback manuel)
HOLIDAYS_COUNTRY=FR
HOLIDAYS_YEARS=2025,2026
PUBLIC_HOLIDAYS=2025-01-01,2025-05-01,2025-12-25

# Optimisation d’itinéraire
GOOGLE_MAPS_API_KEY=

# Sélection géographique
MAX_RADIUS_KM=80
MAX_DAILY_DISTANCE_KM=220
CLUSTER_RADIUS_KM=10

# Génération auto au login
GENERATION_AUTO_ENABLED=True
GENERATION_AUTO_DRY_RUN=False
```

Les paramètres sont lus dans `crm_visites/settings.py` (via `environ.Env.read_env`). Les fichiers `.env` et `.env.prod` ne sont pas versionnés.

## ▶️ Lancer en local

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Ouvrir `http://127.0.0.1:8000`.

## ⚙️ Génération auto J+28 (au login)

- Déclenchée par un signal `user_logged_in` avec un verrou cache (1×/jour)
- Appelle `front.services.ensure_visits_next_4_weeks`
- Respecte: jours ouvrés, fériés, 6 rdv/jour, objectifs annuels, absences
- Slots réassignés chaque jour à: 09:00, 09:30, 10:00, 10:30, 11:00, 11:30, 12:00

Mode “essai à blanc” (ne crée rien en BDD): mettre `GENERATION_AUTO_DRY_RUN=True`.

## 🗺️ Optimisation d’itinéraires

- Sélection “poche” : points filtrés par rayon, cluster le plus dense/proche du départ, puis chaîne (plus proche du précédent) jusqu’à 6
- Ordre final amélioré par 2‑opt (coût Haversine interne, gratuit)
- Coût final (estimation minutes) :
  - Google Distance Matrix/Directions prioritaire
  - Sinon Haversine (50 km/h par défaut)

Afficher rapidement une tournée optimisée:
```bash
python manage.py show_route --commercial "Nom Commercial"
# ou une date précise
python manage.py show_route --commercial "Nom Commercial" --date 2025-09-18
```

## 🔧 Commandes utiles

```bash
# Géocoder les adresses manquantes
python manage.py geocode_addresses

# Afficher une tournée optimisée
python manage.py show_route --commercial "Nom Commercial"

# Purger des données de démo (avec --dry-run pour prévisualiser)
python manage.py purge_demo_data --dry-run
python manage.py purge_demo_data --yes

# Divers (existant dans front/management/commands)
python manage.py init_visit_stats
python manage.py create_responsable_group
python manage.py nettoyer_rdv_anciens
python manage.py generer_rdv_mensuel
python manage.py update_client_objectifs
python manage.py fix_addresses
python manage.py update_scores_hybrides
python manage.py fill_rdv_rs_nom
python manage.py map_commerciaux
```

## 🧪 Tests

- Tests Django classiques (TestCase) présents dans `front/tests.py`
- PyTest supporté si `pytest.ini` est présent
  - Exécution verbeuse: `pytest -vv`
  - Exécution compacte: `pytest -q`

## 🐳 Déploiement Docker (exemple)

Compose web + nginx + MySQL, statiques collectés et servies par nginx.

Exemples de commandes :
```bash
# Démarrer en prod
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Vérifier les services
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod ps

# Tester depuis le conteneur nginx (utiliser IPv4)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec nginx \
  sh -lc 'wget -S -O /dev/null http://127.0.0.1/'
```
Astuce: Si `wget http://localhost/` échoue avec IPv6 (::1), utiliser `127.0.0.1` ou activer `listen [::]:80;` dans la conf nginx.

Collecte des statiques (si nécessaire):
```bash
python manage.py collectstatic --noinput
```

## 🔐 Bonnes pratiques prod

- Mettre `DEBUG=False`, renseigner `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS`
- Cookies sécurisés et redirection HTTPS activés automatiquement si `DEBUG=False`
- `STATIC_ROOT` configuré et `collectstatic` exécuté
- Cache applicatif (Redis conseillé) pour le verrou quotidien
- Clés/API et secrets uniquement via `.env`
- Pour limiter la consommation API de routing :
  - Matrices one‑to‑many uniquement
  - 2‑opt via Haversine
  - Un seul calcul final de coût par tournée

---

© Projet sous licence MIT.

# 🏢 CRM Visites - Gestion Commerciale

Un système de gestion de la relation client (CRM) pour les commerciaux, permettant le suivi des rendez-vous, des objectifs annuels et des questionnaires de satisfaction B2B.

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Technologies utilisées](#-technologies-utilisées)
- [Installation](#-installation)
- [Configuration (.env)](#-configuration-env)
- [Utilisation](#-utilisation)
- [Structure du projet](#-structure-du-projet)
- [Commandes de gestion](#-commandes-de-gestion)
- [Routes web (pages)](#-routes-web-pages)
- [API REST (JSON)](#-api-rest-json)
- [Bonnes pratiques production](#-bonnes-pratiques-production)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

## ✨ Fonctionnalités

### 🎯 Dashboard Principal
- **Vue d'ensemble** des rendez-vous (à venir, récent, à rappeler, notification pour rdv en retard)
- **Interface responsive** (PC, tablette, mobile)
- **Gestion des sessions** avec timeout automatique et avertissement
- **Nettoyage** des RDV anciens non traités

### 📊 Objectifs Annuels
- **Suivi des objectifs** par commercial et par client (A, B, C)
- **KPIs** (réalisés, restants, progression)
- **Filtres** par année et statut
- **Modal client** avec historique
- **Questionnaires B2B** (PDF)
- **Donut de progression** responsive

### 👥 Gestion des Commerciaux
- **Profils** commerciaux et rôles
- **Attribution clients** et performances
- **Absences** (exclusion auto de la planification)

### 📅 Rendez-vous
- **Planification** (statuts: à venir, validé, annulé, gelé)
- **Historique** et commentaires
- **Planification auto J+28** (idempotente, jours ouvrés, plafond 6rdv/jour)

### 👤 Clients
- **Fichier client** `/client_file/`
- **Recherche** et édition
- **Import/Export Excel**
- **Classement** A/B/C pour objectifs

### 🗺️ Géolocalisation
- **Géocodage** Nominatim
- **Planification auto J+28** avec sélection géographique (rayon, clustering) et ordre optimisé (Google/Haversine + 2‑opt)

## 🛠️ Technologies utilisées

### Backend
- **Django 5.2.1**
- **MySQL/SQLite** (piloté via ORM)

### Frontend
- **HTML5/CSS3/JS**
- **Font Awesome**

### Bibliothèques Python principales
- **django-environ** (configuration .env)
- **pandas**, **openpyxl** (Excel)
- **geopy** (carto)
- **requests** (HTTP)
- **xhtml2pdf**, **reportlab**, **html5lib**, **webencodings** (PDF)
- **textblob** (analyse texte)
- **holidays** (jours fériés par pays/année)

## 🚀 Installation

### 1) Cloner et se placer dans le dossier
```bash
git clone https://github.com/votre-username/crm_visites.git
cd crm_visites
```

### 2) Créer et activer un environnement virtuel
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3) Mettre à jour pip (recommandé)
```bash
python -m pip install --upgrade pip
```

### 4) Installer les dépendances Python
```bash
pip install -r requirements.txt
```

Notes d’installation:
- MySQL (mysqlclient) peut nécessiter: 
  - Windows: installer MySQL et ses en-têtes, Visual C++ Build Tools.
  - Linux: `sudo apt-get install default-libmysqlclient-dev build-essential`.
  
Remarque: la génération PDF est assurée par xhtml2pdf/ReportLab uniquement (aucune dépendance système spécifique ajoutée ici).

## ⚙️ Configuration (.env)

Le projet utilise **django-environ**. Créez un fichier `.env` à la racine, à partir de cet exemple:

```env
# Django
DJANGO_SECRET_KEY=votre-cle-secrete
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000

# Base de données (MySQL par défaut)
DB_NAME=crm_visites
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306

# Email (dev par défaut: console)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@rubio.fr
SITE_BASE_URL=http://127.0.0.1:8000

# Jours fériés (optionnels)
HOLIDAYS_COUNTRY=FR
HOLIDAYS_YEARS=2025,2026
# Liste manuelle de secours (fallback si la lib/vars ne sont pas disponibles)
PUBLIC_HOLIDAYS=2025-01-01,2025-05-01,2025-12-25

# Optimisation d'itinéraire
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
ROUTING_USE_ORS=False  # laisser False si vous n'utilisez plus ORS

# Règles de sélection géographique
MAX_RADIUS_KM=60            # rayon max autour du départ
MAX_DAILY_DISTANCE_KM=180   # limite distance cumulée d'une journée
CLUSTER_RADIUS_KM=10        # rayon de clustering pour regrouper une zone

# Génération automatique au login
GENERATION_AUTO_ENABLED=True
GENERATION_AUTO_DRY_RUN=False
```

Les paramètres sont lus dans `crm_visites/settings.py` via `environ.Env.read_env()`.

### Initialiser la base et démarrer
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## 📖 Utilisation
- Ouvrir `http://127.0.0.1:8000`
- Se connecter avec le superutilisateur
- Accéder aux interfaces: `/dashboard`, `/dashboard-responsable`, `/objectif-annuel`, `/client_file`

### Génération automatique des RDV (au login)
- À chaque connexion d’un utilisateur, un job quotidien se déclenche (verrou cache par jour) et appelle `ensure_visits_next_4_weeks`.
- Ce job planifie jusqu’à J+28 en jours ouvrés, plafond 6 RDV/jour/commercial, en sélectionnant d’abord une zone proche (rayon + clustering), puis en optimisant l’ordre (Google/Haversine + 2‑opt) et en réassignant les créneaux.
- Le processus est idempotent (pas de doublon).

### Visualiser rapidement l’itinéraire d’un commercial
```bash
python manage.py show_route --commercial "Commercial 2"
# ou
python manage.py show_route --date 2025-09-18 --commercial "Commercial 2"
```
La commande affiche l'ordre optimisé, les segments, les totaux, et le mode utilisé (GOOGLE/HAVERSINE).

### Structure du projet

crm_visites/                    # package Django (settings, urls, wsgi/asgi)
├── crm_visites/
|   ├── _init_.py              
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── front/                       # app Django principale
|   ├── css/
|   ├── management/                 
│   ├── migrations/              # migrations de l'app
│   ├── templates/               # templates HTML (ex: front/login.html)
│   └── static/                  # assets de l'app (front/css, front/img, ...)
├── nginx/
│   └── conf.d/
│       └── app.conf             # conf Nginx (reverse proxy + /static/)
├── staticfiles/                 # cible de collectstatic (ignoré par git)
├── tools/                       # scripts utilitaires (optionnel)
├── Dockerfile                   # image "web" (gunicorn + app)
├── entrypoint.sh                # boot : migrations, collectstatic, gunicorn
├── docker-compose.yml           # base (build image web)
├── docker-compose.prod.yml      # overrides prod (nginx, volumes, healthchecks)
├── .env.example                 # variables d’exemple (dev)
├── .env.prod.example            # variables d’exemple (prod)
├── .env                         # perso (gitignore)
├── .env.prod                    # prod local (gitignore)
├── .gitignore
├── requirements.txt
├── Makefile                     # raccourcis (optionnel)
├── pytest.ini                   # tests (optionnel)
└── README.md

## 🔧 Commandes de gestion

### Principales
```bash
# Générer les objectifs annuels manquants
python manage.py generate_missing_objectives

# Initialiser les stats de visites
python manage.py init_visit_stats

# Nettoyer les RDV anciens
python manage.py nettoyer_rdv_anciens

# Planifier une tournée commerciale optimisée
python manage.py planifier_tournee_commercial

# Géocoder les adresses clients
python manage.py geocode_addresses

# Créer le groupe responsable
python manage.py create_responsable_group

# Générer des RDV mensuels automatiques
python manage.py generer_rdv_mensuel
```

### Maintenance / Import-Export
```bash
# Corriger les scores de satisfaction
python manage.py fix_satisfaction_scores

# Mettre à jour les objectifs clients
python manage.py update_client_objectifs

# Tester le timeout de session
python manage.py test_session_timeout

# Corriger les adresses
python manage.py fix_addresses

# Mettre à jour les scores hybrides
python manage.py update_scores_hybrides

# Importer des clients depuis Excel
python manage.py migrate_import_clients

# Remplir les noms de clients dans les RDV
python manage.py fill_rdv_rs_nom

# Mapper les commerciaux
python manage.py map_commerciaux
```

## 🚀 Déploiement avec Docker

### Mode développement
Lancer avec base MySQL dans Docker et hot-reload :
```bash
docker compose up -d

## 🌐 Routes web (pages)

- `GET /dashboard/` — Dashboard commercial (HTML)
- `GET /dashboard-responsable/` — Dashboard responsable (HTML)
- `GET /objectif-annuel/` — Objectifs annuels (HTML)
- `GET /historique_rdv/` — Historique des rendez-vous (HTML)
- `GET /historique_rdv_resp/` — Historique responsable (HTML)
- `GET /add_rdv/` — Formulaire d’ajout de rendez-vous (HTML)
- `GET /client_file/` — Fichier client (HTML)
- `GET /profils_commerciaux/` — Profils commerciaux (HTML)
- `GET /fiche_commercial/<id>/` — Détail commercial (HTML)
- `GET /route_optimisee/` — Vue Itinéraire optimisé (HTML)
- `GET /geocoder_adresses/` — Outil de géocodage (HTML)
- `GET /satisfaction_b2b/` — Questionnaires (HTML)

## 🧩 API REST (JSON)

- `GET /api/client-details/<int:client_id>/` — Détails client (lecture)
- `GET /api/rdv-counters/` — Compteurs RDV globaux (lecture)
- `GET /api/rdv-counters-by-client/` — Compteurs RDV par client (lecture)
- `GET /api/rdvs-a-venir/` — RDV à venir (liste, lecture)
- `GET /api/clients-by-commercial/` — Clients d’un commercial (lecture)
- `GET /api/commerciaux/` — Liste des commerciaux (lecture)
- `GET /api/satisfaction-stats/` — Statistiques satisfaction (lecture)
- `GET /api/route-optimisee/<str:date>/` — Itinéraire optimisé JSON pour une date (lecture)
- `GET /api/search-rdv-historique/` — Recherche dans l’historique RDV (lecture)
- `GET /api/capacity/` — Jours ouvrés et capacité (lecture) — params: year, month, daily_quota, cap_to_four_weeks

Méthodes HTTP: sauf mention contraire, ces endpoints sont en GET (lecture seule). Les opérations d’écriture (création/modification/suppression) sont réalisées via les vues web sécurisées (CSRF + login), pas d’API publique POST/PUT/DELETE exposée à ce jour.

Note: versionner l’API (`/api/v1/...`) avant d’introduire des changements incompatibles.

## 🔐 Bonnes pratiques production
- Mettre `DEBUG=False`, compléter `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` dans `.env`
- Servir les statiques: `python manage.py collectstatic` sur un répertoire (`STATIC_ROOT`)
- Activer cookies sécurisés et HTTPS (déjà gérés si `DEBUG=False`)
- Configurer un cache (Redis recommandé) pour le verrou quotidien
 - Jours fériés: la lib `holidays` est utilisée si `HOLIDAYS_COUNTRY` et `HOLIDAYS_YEARS` sont définis; sinon fallback sur `PUBLIC_HOLIDAYS`

## 🤝 Contribuer
1. Fork
2. Branche: `git checkout -b feature/ma-feature`
3. Commits: `git commit -m "feat: description"`
4. Push: `git push origin feature/ma-feature`
5. Ouvrir une Pull Request

## 📄 Licence

Projet sous licence **MIT**. Voir `LICENSE`.
