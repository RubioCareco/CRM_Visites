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
- [API Endpoints](#-api-endpoints)
- [Bonnes pratiques production](#-bonnes-pratiques-production)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

## ✨ Fonctionnalités

### 🎯 Dashboard Principal
- **Vue d'ensemble** des rendez-vous (à venir, récents, à rappeler, en retard)
- **Statistiques** en temps réel avec compteurs dynamiques
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
- **Planification auto J+28** (idempotente, jours ouvrés, plafond 7/jour)

### 👤 Clients
- **Fichier client** `/client_file/`
- **Recherche** et édition
- **Import/Export Excel**
- **Classement** A/B/C pour objectifs

### 🗺️ Géolocalisation
- **Géocodage** Nominatim
- **Planification auto J+28** avec sélection géographique (rayon, clustering) et ordre optimisé (Mapbox + 2‑opt)

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
- **openrouteservice**, **geopy** (carto)
- **requests** (HTTP)
- **xhtml2pdf**, **reportlab**, **weasyprint** (PDF)
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
# source venv/bin/activate
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
- WeasyPrint peut nécessiter des bibliothèques système selon l’OS. Voir la doc officielle si besoin.

## ⚙️ Configuration (.env)

Le projet utilise **django-environ**. Créez un fichier `.env` à la racine, à partir de cet exemple:

```env
# Django
DJANGO_SECRET_KEY=votre-cle-secrete-longue-et-aleatoire
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
MAPBOX_ACCESS_TOKEN=your_mapbox_token
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
- Ce job planifie jusqu’à J+28 en jours ouvrés, plafond 7 RDV/jour/commercial, en sélectionnant d’abord une zone proche (rayon + clustering), puis en optimisant l’ordre (Mapbox + 2‑opt) et en réassignant les créneaux.
- Le processus est idempotent (pas de doublon).

### Visualiser rapidement l’itinéraire d’un commercial
```bash
python manage.py show_route --commercial "Commercial 2"
# ou
python manage.py show_route --date 2025-09-18 --commercial "Commercial 2"
```
La commande affiche l'ordre optimisé, les segments, les totaux, et le mode utilisé (MAPBOX/HAVERSINE).

## 📁 Structure du projet

```
crm_visites/
├── crm_visites/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── front/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── signals.py
│   ├── services.py
│   ├── templates/
│   └── static/
├── manage.py
├── requirements.txt
├── README.md
└── LICENSE
```

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

## 🌐 API Endpoints

### Principaux
- `GET /dashboard/` — Dashboard commercial
- `GET /dashboard-responsable/` — Dashboard responsable
- `GET /objectif-annuel/` — Objectifs annuels
- `GET /historique_rdv/` — Historique des rendez-vous
- `GET /historique_rdv_resp/` — Historique responsable
- `GET /add_rdv/` — Ajouter un rendez-vous
- `GET /client_file/` — Fichier client
- `GET /profils_commerciaux/` — Profils commerciaux
- `GET /fiche_commercial/<id>/` — Détail commercial
- `GET /route_optimisee/` — Itinéraire optimisé
- `GET /geocoder_adresses/` — Géocodage
- `GET /satisfaction_b2b/` — Questionnaires

### API REST
- `GET /api/client-details/<int:client_id>/`
- `GET /api/rdv-counters/`
- `GET /api/rdv-counters-by-client/`
- `GET /api/rdvs-a-venir/`
- `GET /api/clients-by-commercial/`
- `GET /api/commerciaux/`
- `GET /api/satisfaction-stats/`
- `GET /api/route-optimisee/<str:date>/`
- `GET /api/search-rdv-historique/`

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
