# Besoins Non Fonctionnels - CRM Visites

Version: 1.0  
Projet: `crm_visites`  
Date: 2026-02-27

## 1. Objet
Définir les exigences non fonctionnelles de l'applicatif CRM Visites afin de garantir:
- sécurité,
- performance,
- disponibilité,
- robustesse,
- exploitabilité,
- conformité,
- maintenabilité.

## 2. Périmètre
Ces exigences s'appliquent à:
- l'application Django (`front`, `crm_visites`),
- la base de données MySQL,
- les composants d'exposition (Nginx/Gunicorn),
- les intégrations externes (Google, INSEE, email),
- les environnements `dev`, `preview`, `prod`.

## 3. Exigences non fonctionnelles détaillées

## 3.1 Sécurité
- BNF-SEC-01: Toutes les routes métier doivent exiger une authentification.
- BNF-SEC-02: Les contrôles d'autorisation doivent empêcher tout accès hors périmètre commercial.
- BNF-SEC-03: Les endpoints sensibles doivent être protégés CSRF (sauf exceptions documentées).
- BNF-SEC-04: Les actions sensibles doivent être rate-limit (login, reset password, pin/unpin, actions statut).
- BNF-SEC-05: Les cookies session/csrf doivent être configurés en mode sécurisé en production (`Secure`, `HttpOnly`, `SameSite`).
- BNF-SEC-06: Les secrets (clé Django, API keys, credentials) ne doivent jamais être hardcodés.
- BNF-SEC-07: En production, aucune stack trace détaillée ne doit être exposée à l'utilisateur.
- BNF-SEC-08: Les événements sensibles doivent être journalisés de façon traçable (acteur, action, cible, timestamp).

Critères d'acceptation:
- tests d'accès horizontal KO,
- tests de throttling OK,
- configuration sécurité prod validée.

## 3.2 Performance
- BNF-PERF-01: Temps de réponse API nominal < 800 ms (p95) sur endpoints standards (`rdvs-by-date`, recherche).
- BNF-PERF-02: Endpoints lourds (map/optimisation/export) < 3 s (p95) hors dépendance externe dégradée.
- BNF-PERF-03: Le chargement initial des pages principales doit rester fluide sur poste standard (< 3 s hors réseau lent).
- BNF-PERF-04: Les requêtes base doivent être indexées sur colonnes critiques (dates RDV, commercial, client, statuts).
- BNF-PERF-05: Les appels INSEE doivent être mis en cache côté serveur pour réduire latence et quotas.

Critères d'acceptation:
- mesures ponctuelles en preview/prod,
- absence de lenteurs bloquantes sur parcours métier.

## 3.3 Disponibilité et continuité
- BNF-DISP-01: Le service doit rester disponible sur les plages d'usage métier (jours ouvrés).
- BNF-DISP-02: Une route de santé (`/healthz`) doit retourner un statut exploitable.
- BNF-DISP-03: En cas d'échec service externe (INSEE/Google), le CRM doit rester utilisable en mode dégradé (best effort).
- BNF-DISP-04: Les redémarrages applicatifs ne doivent pas corrompre les données métier.

Critères d'acceptation:
- `healthz` monitoré,
- comportement dégradé vérifié sans blocage fonctionnel.

## 3.4 Fiabilité et intégrité des données
- BNF-DATA-01: Les contraintes d'unicité critiques (doublon RDV) doivent être garanties en base.
- BNF-DATA-02: Les opérations métier doivent préserver la cohérence (pas d'état partiel non maîtrisé).
- BNF-DATA-03: Les données saisies doivent être validées côté frontend et côté backend.
- BNF-DATA-04: Les migrations de schéma doivent être versionnées et reproductibles.
- BNF-DATA-05: Les imports/exports doivent détecter et signaler les erreurs de format.

Critères d'acceptation:
- tests de non-régression DB,
- absence d'incohérence fonctionnelle après opérations courantes.

## 3.5 Observabilité et journalisation
- BNF-OBS-01: Les logs doivent permettre d'identifier rapidement la cause d'une erreur.
- BNF-OBS-02: Les logs applicatifs ne doivent pas contenir de données sensibles brutes (secrets, mots de passe, tokens).
- BNF-OBS-03: Les erreurs critiques (500, exceptions métier) doivent être journalisées avec contexte minimal utile.
- BNF-OBS-04: Les actions métier majeures doivent être consultables dans un journal d'activité.

Critères d'acceptation:
- logs exploitables en diagnostic,
- pas de fuite sensible détectée.

## 3.6 UX, accessibilité et responsive
- BNF-UX-01: L'application doit être utilisable sur desktop et mobile (viewport min 390x844).
- BNF-UX-02: Aucun composant critique (boutons, footer, modales, champs) ne doit être masqué ou inaccessible.
- BNF-UX-03: Les retours utilisateur (toasts/messages) doivent être lisibles et non bloquants.
- BNF-UX-04: La cohérence visuelle inter-écrans doit être maintenue (modales, boutons, headers, couleurs).
- BNF-UX-05: Les interactions ne doivent pas dépendre de popups navigateur natifs non contrôlés.

Critères d'acceptation:
- recette responsive validée,
- zéro blocage UX majeur.

## 3.7 Compatibilité
- BNF-COMP-01: Support minimum navigateurs récents: Chrome, Edge.
- BNF-COMP-02: Dégradation acceptable si service externe indisponible.
- BNF-COMP-03: Compatibilité temporaire des anciens paramètres d'URL (`client_id`) tant que migration UUID non finalisée.

## 3.8 Maintenabilité et qualité logicielle
- BNF-MNT-01: Le code doit rester structuré par responsabilités (views/services/utils).
- BNF-MNT-02: Toute évolution critique doit être couverte par tests automatisés ciblés.
- BNF-MNT-03: Les docs techniques doivent être mises à jour à chaque changement structurant (sécurité, routes, règles métier).
- BNF-MNT-04: Les configurations doivent être centralisées via variables d'environnement.
- BNF-MNT-05: Les changements doivent passer par PR avec revue et checklist de non-régression.

Critères d'acceptation:
- tests CI verts,
- documentation cohérente avec le code.

## 3.9 Exploitabilité et déploiement
- BNF-OPS-01: Déploiement reproductible via Docker Compose.
- BNF-OPS-02: Séparation claire des configs `dev/preview/prod`.
- BNF-OPS-03: Les migrations doivent être appliquées automatiquement ou via procédure standard documentée.
- BNF-OPS-04: Les échecs de démarrage (DB indisponible, variable manquante) doivent être explicites dans les logs.
- BNF-OPS-05: Les sauvegardes/restaurations DB doivent être possibles via procédure documentée.

## 3.10 Conformité et confidentialité
- BNF-RGPD-01: Seules les données nécessaires au service doivent être traitées.
- BNF-RGPD-02: Les pages légales (mentions/politique confidentialité) doivent être accessibles en permanence.
- BNF-RGPD-03: La bannière cookies doit refléter l'usage réel (cookies techniques uniquement).
- BNF-RGPD-04: Les exports de données doivent respecter les droits d'accès du rôle connecté.

## 4. Niveaux de sévérité non fonctionnelle
- Critique: impact sécurité/intégrité/disponibilité majeure -> correction immédiate.
- Majeure: impact fort expérience ou performance métier -> correction prioritaire.
- Mineure: gêne limitée sans risque métier direct -> correction planifiée.

## 5. Vérification et preuves attendues
- tests Django automatisés (`manage.py test front -v 2`),
- vérifications manuelles UI/UX mobile et desktop,
- captures DevTools (statuts API, temps réponse),
- logs applicatifs sur scénarios nominal + erreur,
- checklist de non-régression validée avant merge.

## 6. Backlog non fonctionnel recommandé
- BNF-BKL-01: Ajouter des métriques techniques (latence p95 par endpoint).
- BNF-BKL-02: Ajouter monitoring/alerting centralisé (health + erreurs 5xx).
- BNF-BKL-03: Renforcer l'audit trail consultable par rôle.
- BNF-BKL-04: Formaliser objectifs SLO/SLA par environnement.
- BNF-BKL-05: Campagne de tests perf ciblée sur endpoints map/optimisation/export.
