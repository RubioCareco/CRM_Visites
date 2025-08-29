# 🔐 Système de Déconnexion Automatique - CRM RUBIO

## 🎯 **Vue d'ensemble**

Ce système déconnecte automatiquement les utilisateurs après **30 minutes d'inactivité** pour des raisons de sécurité. Une alerte apparaît **5 minutes avant l'expiration** pour permettre de prolonger la session.

## 🏗️ **Architecture implémentée**

### **1. Middleware de sécurité (`front/middleware.py`)**
- **Surveillance continue** : Vérifie l'activité de l'utilisateur à chaque requête
- **Gestion des timestamps** : Enregistre la dernière activité dans la session
- **Déconnexion automatique** : Déconnecte après 30 minutes d'inactivité
- **Alerte préventive** : Affiche un avertissement 5 minutes avant expiration

### **2. Configuration Django (`crm_visites/settings.py`)**
```python
# Middleware activé
'front.middleware.SessionTimeoutMiddleware'

# Configuration des sessions
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
```

### **3. Template d'alerte (`front/templates/front/session_timeout_warning.html`)**
- **Interface responsive** : S'adapte à PC, tablette et mobile
- **Compte à rebours** : Affiche le temps restant en temps réel
- **Actions disponibles** : Prolonger la session ou se déconnecter
- **Animations** : Transitions fluides et modernes

### **4. Vue de prolongation (`front/views.py`)**
- **Endpoint AJAX** : `/extend-session/`
- **Mise à jour automatique** : Remet à zéro le timer d'inactivité
- **Gestion des erreurs** : Retourne des réponses JSON appropriées

## 📱 **Responsive Design**

### **Mode PC (Desktop)**
- Alerte centrée avec boutons côte à côte
- Largeur fixe de 400px
- Espacement généreux pour la lisibilité

### **Mode Tablette (≤768px)**
- Boutons empilés verticalement
- Largeur adaptée à 85% de l'écran
- Taille de police légèrement réduite

### **Mode Mobile (≤480px)**
- Interface optimisée pour petits écrans
- Boutons pleine largeur
- Icônes et textes adaptés

## ⚙️ **Fonctionnement détaillé**

### **Cycle de vie d'une session :**
1. **Connexion** → Timestamp initial enregistré
2. **Activité** → Timestamp mis à jour à chaque action
3. **25ème minute** → Alerte d'expiration affichée
4. **30ème minute** → Déconnexion automatique

### **Actions utilisateur :**
- **Clic sur "Prolonger"** → Session prolongée de 30 minutes
- **Clic sur "Se déconnecter"** → Déconnexion immédiate
- **Inaction** → Déconnexion automatique

## 🧪 **Tests et vérification**

### **Commande de test :**
```bash
# Vérifier la configuration
python manage.py test_session_timeout

# Simuler un timeout
python manage.py test_session_timeout --simulate-timeout
```

### **Test manuel :**
1. Se connecter au dashboard
2. Laisser la page ouverte sans activité
3. Attendre l'apparition de l'alerte (25 min)
4. Tester les boutons de prolongation/déconnexion

## 🔧 **Maintenance et configuration**

### **Modifier la durée de timeout :**
Dans `front/middleware.py` :
```python
self.timeout_minutes = 30      # Durée totale
self.warning_minutes = 5       # Alerte avant expiration
```

### **Modifier le comportement :**
- **Alerte plus précoce** : Augmenter `warning_minutes`
- **Session plus longue** : Augmenter `timeout_minutes`
- **Désactiver l'alerte** : Mettre `warning_minutes = 0`

## 🚨 **Sécurité et bonnes pratiques**

### **Avantages :**
- ✅ **Protection automatique** contre les sessions abandonnées
- ✅ **Conformité RGPD** : Limitation de la durée de session
- ✅ **Sécurité renforcée** : Réduction des risques d'accès non autorisé
- ✅ **Expérience utilisateur** : Alerte préventive et possibilité de prolonger

### **Points d'attention :**
- ⚠️ **Test en production** : Vérifier que les timeouts sont appropriés
- ⚠️ **Monitoring** : Surveiller les déconnexions automatiques
- ⚠️ **Formation utilisateurs** : Expliquer le fonctionnement du système

## 📊 **Monitoring et logs**

### **Informations enregistrées :**
- Timestamp de dernière activité
- Durée d'inactivité
- Actions de prolongation/déconnexion
- Messages d'erreur éventuels

### **Logs disponibles :**
- Messages Django (`messages` framework)
- Redirections automatiques
- Erreurs AJAX de prolongation

## 🔄 **Évolutions futures possibles**

### **Fonctionnalités avancées :**
- **Notifications push** : Alerte même si l'onglet n'est pas actif
- **Historique des sessions** : Suivi des connexions/déconnexions
- **Règles personnalisées** : Timeouts différents par rôle utilisateur
- **Mode "nuit"** : Sessions plus longues en dehors des heures de travail

### **Intégrations :**
- **Audit trail** : Enregistrement des actions de sécurité
- **Rapports** : Statistiques d'utilisation des sessions
- **API** : Endpoints pour la gestion des sessions

## 🎉 **Conclusion**

Le système de déconnexion automatique est maintenant **pleinement opérationnel** et **responsive** sur tous les appareils. Il offre un équilibre parfait entre **sécurité** et **expérience utilisateur**, avec des alertes préventives et la possibilité de prolonger les sessions selon les besoins.

**Sécurité renforcée, utilisateurs satisfaits !** 🚀✨ 