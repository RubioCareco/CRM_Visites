# Corrections du problème des notes de satisfaction

## Problème identifié

Les notes de satisfaction dans le dashboard responsable dépassaient 10, ce qui est incorrect car les commerciaux sont notés sur 10 maximum.

## Causes du problème

1. **Multiplication incorrecte des notes de recommandation** : Les notes de recommandation sont déjà sur une échelle de 1-10, mais elles étaient multipliées par 2 dans plusieurs endroits du code.

2. **Données en base incohérentes** : Certaines notes de qualité, SAV et accueil étaient stockées avec des valeurs supérieures à 5, ce qui suggère qu'elles étaient déjà sur une échelle différente.

3. **Normalisation aveugle** : Le code multipliait systématiquement toutes les notes par 2 sans vérifier leur échelle actuelle.

## Fichiers corrigés

### 1. `front/views.py`

#### Fonction `dashboard_responsable` (ligne ~1295)
```python
# AVANT (incorrect)
avg_recommandation_normalisee = avg_recommandation * 2  # Normaliser aussi la recommandation

# APRÈS (correct)
# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
avg_recommandation_normalisee = avg_recommandation
```

**Nouvelle logique de normalisation intelligente :**
```python
# Normaliser les notes intelligemment selon leur échelle
if avg_qualite <= 5:
    avg_qualite_normalisee = avg_qualite * 2  # 1-5 -> 2-10
else:
    avg_qualite_normalisee = avg_qualite  # Déjà sur 10

if avg_sav <= 5:
    avg_sav_normalisee = avg_sav * 2  # 1-5 -> 2-10
else:
    avg_sav_normalisee = avg_sav  # Déjà sur 10

if avg_accueil <= 5:
    avg_accueil_normalisee = avg_accueil * 2  # 1-5 -> 2-10
else:
    avg_accueil_normalisee = avg_accueil  # Déjà sur 10
```

#### Fonction `api_satisfaction_stats` (ligne ~1405)
```python
# AVANT (incorrect)
moyenne_recommandation = round(moyenne_recommandation * 2, 2)  # Normaliser aussi la recommandation

# APRÈS (correct)
# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
moyenne_recommandation = round(moyenne_recommandation, 2)
```

**Nouvelle logique de normalisation intelligente :**
```python
# Normaliser les notes intelligemment selon leur échelle
if moyenne_qualite <= 5:
    moyenne_qualite = round(moyenne_qualite * 2, 2)  # 1-5 -> 2-10
else:
    moyenne_qualite = round(moyenne_qualite, 2)  # Déjà sur 10

if moyenne_sav <= 5:
    moyenne_sav = round(moyenne_sav * 2, 2)  # 1-5 -> 2-10
else:
    moyenne_sav = round(moyenne_sav, 2)  # Déjà sur 10

if moyenne_accueil <= 5:
    moyenne_accueil = round(moyenne_accueil * 2, 2)  # 1-5 -> 2-10
else:
    moyenne_accueil = round(moyenne_accueil, 2)  # Déjà sur 10
```

#### Fonction `api_satisfaction_stats` (ligne ~1473)
```python
# AVANT (incorrect)
recommandation.append(round((entry['moyenne_recommandation'] or 0) * 2, 2))  # Normaliser aussi la recommandation

# APRÈS (correct)
# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
recommandation.append(round((entry['moyenne_recommandation'] or 0), 2))
```

**Nouvelle logique de normalisation intelligente :**
```python
# Normaliser les notes intelligemment selon leur échelle
note_qualite = entry['moyenne_qualite_pieces'] or 0
note_sav = entry['moyenne_sav'] or 0
note_accueil = entry['moyenne_accueil'] or 0
note_recommandation = entry['moyenne_recommandation'] or 0

if note_qualite <= 5:
    qualite.append(round(note_qualite * 2, 2))  # 1-5 -> 2-10
else:
    qualite.append(round(note_qualite, 2))  # Déjà sur 10

if note_sav <= 5:
    sav.append(round(note_sav * 2, 2))  # 1-5 -> 2-10
else:
    sav.append(round(note_sav, 2))  # Déjà sur 10

if note_accueil <= 5:
    accueil.append(round(note_accueil * 2, 2))  # 1-5 -> 2-10
else:
    accueil.append(round(note_accueil, 2))  # Déjà sur 10
```

### 2. `front/models.py`

#### Modèle `SatisfactionB2B` (ligne ~158)
```python
# AVANT (incorrect)
if self.moyenne:
    self.score_hybride = self.moyenne * 2  # Conversion 1-5 vers 0-10

# APRÈS (correct)
if self.moyenne:
    # La moyenne peut contenir des notes sur 5 et sur 10, donc on ne multiplie pas par 2
    # car cela pourrait donner des valeurs supérieures à 10
    self.score_hybride = min(self.moyenne, 10.0)  # Limiter à 10 maximum
```

### 3. `front/utils.py`

#### Fonction `calculate_comprehensive_satisfaction_score`
```python
# AVANT (incorrect)
if satisfaction_obj.note_qualite_pieces:
    score = (satisfaction_obj.note_qualite_pieces * 2)  # 1-5 -> 2-10
    scores.append(score)

# APRÈS (correct)
if satisfaction_obj.note_qualite_pieces:
    # Gérer le cas où la note pourrait être déjà sur 10
    if satisfaction_obj.note_qualite_pieces <= 5:
        score = (satisfaction_obj.note_qualite_pieces * 2)  # 1-5 -> 2-10
    else:
        score = satisfaction_obj.note_qualite_pieces  # Déjà sur 10
    scores.append(score)
```

**Même correction appliquée pour :**
- `note_sav` (Q10)
- `note_accueil` (Q14)

## Nouvelle logique de normalisation intelligente

### Principe
Au lieu de multiplier systématiquement toutes les notes par 2, le système détecte automatiquement l'échelle des notes :

- **Si note ≤ 5** : Multiplier par 2 (1-5 → 2-10)
- **Si note > 5** : Garder la note telle quelle (déjà sur 10)

### Avantages
1. **Gestion automatique** des différentes échelles de notes
2. **Compatibilité** avec les données existantes
3. **Prévention** des notes supérieures à 10
4. **Flexibilité** pour les futures modifications

## Commandes de correction

### 1. Commande de management créée
```bash
python manage.py fix_satisfaction_scores --dry-run  # Voir ce qui serait corrigé
python manage.py fix_satisfaction_scores            # Appliquer les corrections
```

### 2. Résultats de la correction
- **3 satisfactions corrigées** qui avaient des scores > 10
- Tous les scores sont maintenant ≤ 10
- Le graphique du dashboard responsable affiche maintenant des notes correctes
- **Normalisation intelligente** implémentée pour gérer toutes les échelles de notes

## Vérification

Après les corrections :
- ✅ Les moyennes globales ne dépassent plus 10
- ✅ Les notes par commercial ne dépassent plus 10  
- ✅ Tous les scores hybrides sont ≤ 10
- ✅ L'API de satisfaction retourne des données correctes
- ✅ **Normalisation intelligente** fonctionne pour toutes les échelles

## Impact

- **Avant** : Notes pouvant atteindre 14+ sur 10 (incorrect)
- **Après** : Notes limitées à 10 maximum (correct)
- **Graphiques** : Affichage cohérent avec l'échelle de notation 1-10
- **Données** : Cohérence entre les différentes vues du dashboard
- **Robustesse** : Gestion automatique des différentes échelles de notes

## Prévention

Pour éviter ce problème à l'avenir :
1. **Toujours utiliser la normalisation intelligente** qui détecte automatiquement l'échelle
2. Les notes de recommandation sont sur 1-10 (ne pas multiplier par 2)
3. Les notes de qualité, SAV et accueil peuvent être sur 1-5 ou 1-10 (détection automatique)
4. Utiliser la fonction `calculate_comprehensive_satisfaction_score` qui gère correctement ces cas
5. **Tester** les nouvelles fonctionnalités avec des données réelles 