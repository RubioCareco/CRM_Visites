# 🏢 CRM Visites - Gestion Commerciale

Un système de gestion de la relation client (CRM) spécialement conçu pour les commerciaux, permettant le suivi des rendez-vous, des objectifs annuels et des questionnaires de satisfaction.

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
- **Vue d'ensemble** des rendez-vous (à venir, récents, à rappeler)
- **Statistiques** en temps réel
- **Interface responsive** adaptée à tous les appareils
- **Gestion des sessions** avec timeout automatique

### 📊 Objectifs Annuels
- **Suivi des objectifs** par commercial et par client
- **KPIs détaillés** (objectifs réalisés, restants, pourcentage)
- **Filtres avancés** par année et statut
- **Modal de détails client** avec historique complet
- **Questionnaires de satisfaction** intégrés

### 👥 Gestion des Commerciaux
- **Profils commerciaux** avec photos et informations
- **Attribution des clients** par commercial
- **Rôles et permissions** (commercial, responsable)
- **Statistiques individuelles**

### 📅 Gestion des Rendez-vous
- **Planification** de nouveaux RDV
- **Statuts multiples** (planifié, terminé, annulé, absent)
- **Historique complet** des visites
- **Optimisation des tournées** commerciales

### 👤 Gestion des Clients
- **Fichier client** (`/client-file/`) - Interface complète de gestion des clients
- **Recherche avancée** de clients
- **Modification** des informations client
- **Historique détaillé** des interactions
- **Modal de consultation** client intégrée

### 📝 Questionnaires de Satisfaction
- **Génération automatique** de questionnaires B2B
- **Scores hybrides** et moyennes
- **Export PDF** des résultats
- **Suivi de la satisfaction** client

### 🗺️ Géolocalisation
- **Géocodage automatique** des adresses
- **Optimisation des itinéraires**

## 🛠️ Technologies utilisées

### Backend
- **Django 5.2.1** - Framework web Python
- **SQLite/MySQL** - Base de données
- **Django ORM** - Gestion des données
- **Django Sessions** - Authentification

### Frontend
- **HTML5/CSS3** - Interface utilisateur
- **JavaScript ES6+** - Interactivité
- **Font Awesome** - Icônes
- **Responsive Design** - Adaptation mobile/tablette

### Bibliothèques Python
- **Pandas** - Manipulation de données
- **NumPy** - Calculs numériques
- **Geopy** - Géolocalisation
- **WeasyPrint** - Génération PDF
- **ReportLab** - Rapports avancés
- **OpenRouteService** - Optimisation d'itinéraires

## 🚀 Installation

### Prérequis
- Python 3.8+
- pip
- Git

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

6. **Lancer le serveur de développement**
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
- **Admin Django** : http://localhost:8000/admin

### Première utilisation
1. Se connecter avec le superutilisateur créé
2. Créer des commerciaux via l'interface admin
3. Importer des clients via les commandes de gestion
4. Configurer les objectifs annuels

### Rôles utilisateurs
- **Responsable** : Accès complet, gestion des commerciaux
- **Commercial** : Accès à ses clients et objectifs

## 📁 Structure du projet

```
crm_visites/
├── crm_visites/          # Configuration Django
│   ├── settings.py       # Paramètres du projet
│   ├── urls.py          # URLs principales
│   └── wsgi.py          # Configuration WSGI
├── front/               # Application principale
│   ├── models.py        # Modèles de données
│   ├── views.py         # Vues et logique métier
│   ├── urls.py          # URLs de l'application
│   ├── templates/       # Templates HTML
│   ├── static/          # Fichiers statiques (CSS, JS, images)
│   └── management/      # Commandes personnalisées
├── requirements.txt     # Dépendances Python
├── manage.py           # Script de gestion Django
└── README.md           # Ce fichier
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

# Planifier une tournée commerciale
python manage.py planifier_tournee_commercial

# Géocoder les adresses
python manage.py geocode_addresses

# Créer le groupe responsable
python manage.py create_responsable_group
```

### Commandes de maintenance
```bash
# Corriger les scores de satisfaction
python manage.py fix_satisfaction_scores

# Mettre à jour les objectifs clients
python manage.py update_client_objectifs

# Tester le timeout de session
python manage.py test_session_timeout
```

## 🌐 API Endpoints

### Endpoints principaux
- `GET /dashboard/` - Dashboard principal
- `GET /objectif-annuel/` - Interface des objectifs annuels
- `GET /historique_rdv/` - Historique des rendez-vous
- `GET /add_rdv/` - Ajouter un rendez-vous
- `GET /client-file/` - Fichier client (gestion complète)
- `GET /profils-commerciaux/` - Profils des commerciaux
- `GET /dashboard-responsable/` - Dashboard responsable

### API REST
- `GET /api/client-details/<int:client_id>/` - Détails d'un client
- `POST /api/rdv/` - Créer un rendez-vous
- `GET /api/stats/` - Statistiques commerciales

## 🤝 Contribuer

### Comment contribuer
1. Fork le projet
2. Créer une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

### Standards de code
- Suivre les conventions PEP 8 pour Python
- Commenter le code complexe
- Ajouter des tests pour les nouvelles fonctionnalités
- Mettre à jour la documentation

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

**Développé avec ❤️ pour optimiser la gestion commerciale**
