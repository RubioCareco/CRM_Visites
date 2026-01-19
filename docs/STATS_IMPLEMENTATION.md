# Implémentation des Statistiques de Visites Annuelles

## Vue d'ensemble

Cette implémentation ajoute un système de suivi automatique des objectifs annuels de visites par client et commercial, basé sur le classement client (A=10 visites/an, B=5 visites/an, C=1 visite/an).

## Architecture

### 1. Modèle de données

**Table `client_visit_stats`** :
- `client_id` : Référence vers le client
- `commercial_id` : Référence vers le commercial
- `annee` : Année de suivi
- `visites_valides` : Nombre de visites validées cette année
- `objectif` : Objectif annuel basé sur le classement client
- `updated_at` : Timestamp de dernière mise à jour

**Contraintes** :
- Clé unique sur `(client_id, commercial_id, annee)`
- Index sur `(client_id, annee)` et `(commercial_id, annee)`

### 2. Signaux Django

**Automatisation** :
- `post_save` sur `Rendezvous` : Met à jour les stats quand un RDV change de statut
- `post_delete` sur `Rendezvous` : Recalcule les stats quand un RDV est supprimé

**Logique** :
- Détection automatique du classement client (A/B/C)
- Calcul en temps réel des visites validées
- Mise à jour atomique des statistiques

### 3. Commandes de management

**`init_visit_stats`** :
- Initialise les statistiques pour une année donnée
- Options : `--annee`, `--force`
- Récupère le classement client depuis la base
- Calcule les visites validées existantes

**`test_signals`** :
- Teste le fonctionnement des signaux
- Crée/supprime un RDV de test
- Vérifie la mise à jour des statistiques

## Utilisation

### Initialisation

```bash
# Initialiser les stats pour l'année courante
python manage.py init_visit_stats

# Initialiser pour une année spécifique
python manage.py init_visit_stats --annee 2024

# Forcer la réinitialisation
python manage.py init_visit_stats --annee 2024 --force
```

### Test des signaux

```bash
python manage.py test_signals
```

### Dans le code

```python
from front.models import ClientVisitStats

# Récupérer les stats d'un client
stats = ClientVisitStats.objects.get(
    client=client,
    commercial=commercial,
    annee=2024
)

# Accéder aux données
print(f"Visites: {stats.visites_valides}/{stats.objectif}")
print(f"Ratio: {stats.ratio}")  # Propriété calculée
```

## Intégration avec le Dashboard

Le dashboard utilise maintenant les statistiques pré-calculées au lieu de les calculer à la volée :

- **Performance** : Pas de requêtes COUNT() coûteuses
- **Fallback** : Retour au calcul à la volée si les stats ne sont pas disponibles
- **Compatibilité** : Fonctionne même si la table n'existe pas encore

## Maintenance

### Mise à jour automatique
Les signaux maintiennent les statistiques à jour en temps réel.

### Recalage périodique
Recommandé : Tâche cron/job nocturne pour corriger d'éventuels écarts :

```python
# Exemple de tâche de maintenance
python manage.py init_visit_stats --annee $(date +%Y)
```

### Monitoring
Vérifier régulièrement :
- Cohérence entre `Rendezvous` et `ClientVisitStats`
- Performance des requêtes sur la table de stats
- Espace disque utilisé

## Avantages

1. **Performance** : Accès instantané aux objectifs annuels
2. **Scalabilité** : Pas d'impact sur les requêtes du dashboard
3. **Fiabilité** : Mise à jour automatique et atomique
4. **Flexibilité** : Support multi-années et multi-commerciaux
5. **Audit** : Historique des objectifs et réalisations

## Limitations

1. **Stockage** : Table supplémentaire à maintenir
2. **Complexité** : Signaux à surveiller pour les performances
3. **Synchronisation** : Risque d'écart en cas de panne des signaux

## Évolutions futures

- Cache Redis pour les lectures fréquentes
- Agrégats par mois/semaine
- Alertes automatiques sur les objectifs non atteints
- Export des statistiques en CSV/Excel 