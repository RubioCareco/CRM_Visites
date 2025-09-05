# 🏢 CRM Visites - Gestion Commerciale

Un système de gestion de la relation client (CRM) spécialement conçu pour les commerciaux, permettant le suivi des rendez-vous, des objectifs annuels et des questionnaires de satisfaction B2B.

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Technologies utilisées](#-technologies-utilisées)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [Structure du projet](#-structure-du-projet)
- [Commandes de gestion](#-commandes-de-gestion)
- [API Endpoints](#-api-endpoints)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

## ✨ Fonctionnalités

### 🎯 Dashboard Principal
- **Vue d'ensemble** des rendez-vous (à venir, récents, à rappeler, en retard)
- **Statistiques** en temps réel avec compteurs dynamiques
- **Interface responsive** adaptée à tous les appareils (PC, tablette, mobile)
- **Gestion des sessions** avec timeout automatique et avertissement
- **Nettoyage automatique** des RDV anciens non traités

### 📊 Objectifs Annuels
- **Suivi des objectifs** par commercial et par client (A, B, C)
- **KPIs détaillés** (objectifs réalisés, restants, pourcentage de progression)
- **Filtres avancés** par année et statut (atteint/non atteint)
- **Modal de détails client** avec historique complet des visites
- **Questionnaires de satisfaction** intégrés avec scores hybrides
- **Donut de progression** animé et responsive

### 👥 Gestion des Commerciaux
- **Profils commerciaux** avec photos, informations personnelles et géolocalisation
- **Attribution des clients** par commercial avec gestion des rôles
- **Rôles et permissions** (commercial, responsable, admin)
- **Statistiques individuelles** et performances
- **Gestion des absences** avec switch on/off
- **Géolocalisation** du point de départ pour optimiser les tournées

### 📅 Gestion des Rendez-vous
- **Planification** de nouveaux RDV avec validation automatique
- **Statuts multiples** (à venir, validé, annulé, gelé, en retard)
- **Historique complet** des visites avec commentaires
- **Optimisation des tournées** commerciales avec OpenRouteService
- **Géocodage automatique** des adresses clients
- **Génération automatique** de RDV mensuels

### 👤 Gestion des Clients
- **Fichier client** (`/client-file/`) - Interface complète de gestion
- **Recherche avancée** de clients avec filtres multiples
- **Modification** des informations client en temps réel
- **Historique détaillé** des interactions et RDV
- **Import/Export Excel** des données clients
- **Classification clients** (A, B, C) pour les objectifs

### 📝 Questionnaires de Satisfaction B2B
- **Génération automatique** de questionnaires après chaque RDV
- **Scores hybrides** et moyennes calculées automatiquement
- **Export PDF** des résultats avec mise en page professionnelle
- **Suivi de la satisfaction** client avec analyse de sentiment
- **UUID sécurisés** pour chaque questionnaire
- **Statistiques détaillées** par commercial et période

### 🗺️ Géolocalisation et Optimisation
- **Géocodage automatique** des adresses avec Nominatim
- **Optimisation des itinéraires** avec OpenRouteService
- **Calcul de distances** Haversine pour les tournées
- **Cartes interactives** des clients et points de visite
- **Gestion des points de départ** par commercial

### 📊 Rapports et Analytics
- **Export Excel** des satisfactions et statistiques
- **Graphiques de performance** par commercial
- **Statistiques de satisfaction** avec filtres temporels
- **Rapports de tournées** optimisées
- **Suivi des objectifs** avec métriques détaillées

## 🛠️ Technologies utilisées

### Backend
- **Django 5.2.1** - Framework web Python
- **SQLite/MySQL** - Base de données (mysqlclient)
- **Django ORM** - Gestion des données et migrations
- **Django Sessions** - Authentification et gestion des sessions
- **Django Admin** - Interface d'administration

### Frontend
- **HTML5/CSS3** - Interface utilisateur responsive
- **JavaScript ES6+** - Interactivité et animations
- **Font Awesome 6.5.0** - Icônes et interface
- **Responsive Design** - Adaptation mobile/tablette/desktop
- **CSS Grid/Flexbox** - Layouts modernes

### Bibliothèques Python
- **Pandas** - Manipulation de données Excel et CSV
- **OpenRouteService** - Optimisation d'itinéraires
- **Geopy** - Géocodage d'adresses (Nominatim)
- **TextBlob** - Analyse de sentiment pour les questionnaires
- **Requests** - Appels API HTTP
- **XHTML2PDF** - Génération de PDF
- **OpenPyXL** - Lecture/écriture de fichiers Excel
- **Pytz** - Gestion des fuseaux horaires
- **UUID** - Identifiants uniques sécurisés
- **Base64** - Encodage des PDF en base64

### Services externes
- **OpenRouteService API** - Optimisation d'itinéraires
- **Nominatim** - Géocodage d'adresses
- **SMTP** - Envoi d'emails automatiques

## 🚀 Installation

### Prérequis
- Python 3.8+
- pip
- Git
- Clé API OpenRouteService (optionnelle)

### Étapes d'installation

1. **Cloner le repository**
```bash
git clone https://github.com/votre-username/crm_visites.git
cd crm_visites
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer la base de données**
```bash
python manage.py makemigrations
python manage.py migrate
```

5. **Créer un superutilisateur**
```bash
python manage.py createsuperuser
```

6. **Initialiser les données**
```bash
python manage.py create_responsable_group
python manage.py init_visit_stats
```

7. **Lancer le serveur de développement**
```bash
python manage.py runserver
```

## ⚙️ Configuration

### Variables d'environnement
Créer un fichier `.env` à la racine du projet :

```env
DEBUG=True
SECRET_KEY=votre-clé-secrète
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
ORS_API_KEY=votre-clé-openrouteservice
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=votre-mot-de-passe-app
```

### Configuration de la base de données
Dans `crm_visites/settings.py`, configurer votre base de données :

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## 📖 Utilisation

### Accès à l'application
- **URL** : http://localhost:8000
- **Interface commerciale** : http://localhost:8000/dashboard
- **Interface responsable** : http://localhost:8000/dashboard-responsable
- **Admin Django** : http://localhost:8000/admin

### Première utilisation
1. Se connecter avec le superutilisateur créé
2. Créer des commerciaux via l'interface admin
3. Importer des clients via les commandes de gestion
4. Configurer les objectifs annuels
5. Géocoder les adresses clients

### Rôles utilisateurs
- **Admin** : Accès complet, gestion système
- **Responsable** : Accès complet, gestion des commerciaux
- **Commercial** : Accès à ses clients et objectifs

## 📁 Structure du projet

```
crm_visites/
├── crm_visites/          # Configuration Django
│   ├── settings.py       # Paramètres du projet
│   ├── urls.py          # URLs principales
│   ├── wsgi.py          # Configuration WSGI
│   └── asgi.py          # Configuration ASGI
├── front/               # Application principale
│   ├── models.py        # Modèles de données (8 modèles)
│   ├── views.py         # Vues et logique métier (50+ vues)
│   ├── urls.py          # URLs de l'application
│   ├── admin.py         # Configuration admin Django
│   ├── signals.py       # Signaux automatiques
│   ├── services.py      # Services externes (géolocalisation)
│   ├── utils.py         # Utilitaires et calculs
│   ├── middleware.py    # Middleware personnalisé
│   ├── templates/       # Templates HTML (25+ templates)
│   ├── static/          # Fichiers statiques
│   │   ├── css/         # Styles CSS (20+ fichiers)
│   │   ├── img/         # Images et logos
│   │   └── js/          # JavaScript
│   └── management/      # Commandes personnalisées (15+ commandes)
├── requirements.txt     # Dépendances Python (50+ packages)
├── manage.py           # Script de gestion Django
├── README.md           # Documentation
└── LICENSE             # Licence MIT
```

## 🔧 Commandes de gestion

### Commandes principales
```bash
# Générer les objectifs annuels manquants
python manage.py generate_missing_objectives

# Initialiser les statistiques de visites
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

### Commandes de maintenance
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
```

### Commandes d'import/export
```bash
# Importer des clients depuis Excel
python manage.py migrate_import_clients

# Remplir les noms de clients dans les RDV
python manage.py fill_rdv_rs_nom

# Mapper les commerciaux
python manage.py map_commerciaux
```

## 🌐 API Endpoints

### Endpoints principaux
- `GET /dashboard/` - Dashboard principal commercial
- `GET /dashboard-responsable/` - Dashboard responsable
- `GET /objectif-annuel/` - Interface des objectifs annuels
- `GET /historique_rdv/` - Historique des rendez-vous
- `GET /historique_rdv_resp/` - Historique responsable
- `GET /add_rdv/` - Ajouter un rendez-vous
- `GET /client_file/` - Fichier client (gestion complète)
- `GET /profils_commerciaux/` - Profils des commerciaux
- `GET /fiche_commercial/<id>/` - Fiche détaillée commercial
- `GET /route_optimisee/` - Optimisation d'itinéraires
- `GET /geocoder_adresses/` - Géocodage d'adresses
- `GET /satisfaction_b2b/` - Questionnaires de satisfaction

### API REST
- `GET /api/client-details/<int:client_id>/` - Détails d'un client
- `GET /api/rdv-counters/` - Compteurs de RDV
- `GET /api/rdv-counters-by-client/` - Compteurs par client
- `GET /api/rdvs-a-venir/` - RDV à venir
- `GET /api/clients-by-commercial/` - Clients par commercial
- `GET /api/commerciaux/` - Liste des commerciaux
- `GET /api/satisfaction-stats/` - Statistiques satisfaction
- `GET /api/route-optimisee/<str:date>/` - Itinéraire optimisé
- `GET /api/search-rdv-historique/` - Recherche historique RDV

### Endpoints de gestion
- `POST /import-clients-excel/` - Import clients Excel
- `GET /export-satisfactions-excel/` - Export satisfactions
- `GET /search-clients/` - Recherche clients
- `GET /search-clients-table/` - Recherche table clients

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

**Développé avec ❤️ pour optimiser la gestion commerciale**
