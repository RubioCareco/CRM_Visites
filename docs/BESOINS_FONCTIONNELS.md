# Besoins Fonctionnels - CRM Visites

Version: 1.1  
Projet: `crm_visites`  
Date: 2026-02-27

## 1. Objet
Formaliser les besoins fonctionnels de l'application CRM Visites afin de:
- cadrer ce que le produit doit faire,
- aligner métier / développement / recette,
- servir de référence de priorisation et d'acceptation.

## 2. Contexte
Le CRM Visites permet:
- le pilotage quotidien des rendez-vous commerciaux,
- l'organisation de tournées clients,
- le suivi de performance (objectifs annuels),
- la collecte et l'exploitation de la satisfaction B2B.

## 3. Acteurs et rôles
- `Commercial`
- `Responsable commercial`
- `Administrateur` (mêmes capacités métier que responsable + administration)
- `Système` (automatisation, notifications, journalisation)

## 4. Périmètre fonctionnel
Inclus:
- authentification / session / reset password,
- dashboards commercial et responsable,
- gestion clients (liste, ajout, édition, import),
- gestion rendez-vous (création, statut, commentaires, épinglage),
- historique commercial et responsable,
- objectifs annuels,
- satisfaction B2B (formulaire, PDF, export),
- APIs métier support.

Hors périmètre:
- analytics marketing,
- paiement/facturation,
- campagne email marketing,
- IAM entreprise externe (SSO).

## 5. Règles métier transverses
- RGT-01: Toute page métier nécessite une session authentifiée.
- RGT-02: Un commercial ne consulte/modifie que son périmètre.
- RGT-03: Un responsable/admin peut piloter plusieurs commerciaux.
- RGT-04: Les actions sensibles sont tracées.
- RGT-05: Les rendez-vous sont uniques par `(commercial, client, date, heure)`.
- RGT-06: Pour créer un RDV, `date + heure + client` sont obligatoires.
- RGT-07: Le statut RDV appartient à `a_venir`, `valide`, `annule`, `gele`.
- RGT-08: Si commercial absent, ajout/suppression de RDV et remplacement tournée sont désactivés.
- RGT-09: Les cookies utilisés sont techniques et nécessaires au fonctionnement.
- RGT-10: Les flux doivent privilégier les UUID (compatibilité legacy maintenue si nécessaire).

## 6. Besoins fonctionnels détaillés

## 6.1 Authentification et session
- BF-AUTH-01 Connexion par email/mot de passe.
- BF-AUTH-02 Redirection post-login selon rôle:
  - commercial -> `dashboard_test`,
  - responsable/admin -> `dashboard_responsable`.
- BF-AUTH-03 Déconnexion avec invalidation de session.
- BF-AUTH-04 Reset password avec message neutre (pas d'énumération).
- BF-AUTH-05 Limitation du reset (anti-abus).
- BF-AUTH-06 Timeout session + prolongation contrôlée (`extend-session`).

Critères d'acceptation:
- aucun accès métier sans session,
- erreurs lisibles, sans fuite technique.

## 6.2 Dashboard commercial (`dashboard_test`)
- BF-DBTC-01 Afficher le calendrier mensuel des RDV.
- BF-DBTC-02 Afficher les 3 vues: `Visites à venir`, `Visites récentes`, `Visites annulées`.
- BF-DBTC-03 Ouvrir la liste des RDV d'un jour au clic.
- BF-DBTC-04 Ouvrir la modal client depuis un RDV.
- BF-DBTC-05 Changer le statut du RDV (valider/annuler) depuis la modal.
- BF-DBTC-06 Afficher un toast d'alerte des RDV en retard (date < aujourd'hui non traités) à la connexion.
- BF-DBTC-07 Filtrer par plage de dates via modal filtres.
- BF-DBTC-08 Rechercher client/entreprise via barre de recherche.

Critères d'acceptation:
- aucune erreur 500 sur parcours nominal,
- compteur retard exact,
- feedback visuel clair (toasts).

## 6.3 Cartographie et tournée
- BF-MAP-01 Charger la carte des clients pour une date.
- BF-MAP-02 Ajouter un client depuis popup marker à la sélection.
- BF-MAP-03 Retirer un client depuis la sélection.
- BF-MAP-04 Synchroniser l'état popup (`Ajouter`/`Ajouté`) avec le panel de sélection.
- BF-MAP-05 Vider complètement la sélection.
- BF-MAP-06 Valider la tournée avec confirmation custom.
- BF-MAP-07 Afficher le résultat (créés/mis à jour/supprimés) avec toast succès/erreur.
- BF-MAP-08 Bloquer les actions de remplacement tournée sur date passée.

Critères d'acceptation:
- sélection stable et cohérente,
- confirmation non-native (pas `window.confirm` navigateur),
- pas de perte silencieuse de données tournée.

## 6.4 Gestion des rendez-vous (`add_rdv`)
- BF-RDV-01 Créer un RDV avec champs obligatoires contrôlés.
- BF-RDV-02 Gérer les erreurs fonctionnelles:
  - champs manquants,
  - doublon,
  - utilisateur absent/non autorisé.
- BF-RDV-03 Persister objet et commentaire (si fournis).
- BF-RDV-04 Afficher toast succès puis redirection différée vers l'origine (`next`).
- BF-RDV-05 Préremplir client/commercial selon contexte d'entrée.
- BF-RDV-06 Depuis `objectif_annuel` (responsable): commercial verrouillé sur celui du client.
- BF-RDV-07 Utiliser `client_uuid` en priorité; fallback legacy `client_id` maintenu.
- BF-RDV-08 Supporter un mode `dry_run` sans écriture DB.

Critères d'acceptation:
- création fiable et idempotence sur doublons,
- préremplissage sans valeurs parasites (`None`).

## 6.5 Commentaires RDV et épinglage
- BF-PIN-01 Ajouter un commentaire sur un RDV.
- BF-PIN-02 Épingler/désépingler immédiatement un commentaire.
- BF-PIN-03 Afficher les commentaires épinglés sur la fiche client.
- BF-PIN-04 Permettre la suppression d'un pin.
- BF-PIN-05 Limiter l'abus pin/unpin (rate-limit).
- BF-PIN-06 Présenter les pins en rendu visuel distinctif (post-it).

Critères d'acceptation:
- action instantanée,
- cohérence d'affichage entre vues.

## 6.6 Gestion clients
- BF-CLI-01 Lister les clients (pagination + recherche + filtres).
- BF-CLI-02 Afficher la fiche client (modal).
- BF-CLI-03 Modifier un client avec contrôle d'accès.
- BF-CLI-04 Ajouter un client manuellement.
- BF-CLI-05 Contrôler SIRET:
  - chiffres uniquement,
  - max 14,
  - Luhn JS,
  - feedback dynamique de longueur.
- BF-CLI-06 Vérifier SIRET côté backend (14 + Luhn Python).
- BF-CLI-07 Appeler INSEE via backend (best effort) si SIRET valide.
- BF-CLI-08 En cas d'échec INSEE, conserver un parcours non bloquant.
- BF-CLI-09 Importer des clients via Excel.

Critères d'acceptation:
- création client possible même sans retour INSEE,
- messages utilisateur explicites.

## 6.7 Objectifs annuels
- BF-OBJ-01 Commercial: consulter KPI (objectif/réalisé/restant/progression).
- BF-OBJ-02 Responsable/admin: sélectionner un commercial et visualiser ses KPI/clients.
- BF-OBJ-03 Filtrer par période (année).
- BF-OBJ-04 Planifier un RDV depuis la fiche client objectif.
- BF-OBJ-05 Conserver le contexte au retour (`year`, `commercial_id`, `next`).

Critères d'acceptation:
- changement de commercial fiable,
- navigation contextuelle correcte.

## 6.8 Historique RDV commercial (`historique_rdv`)
- BF-HISTC-01 Afficher les onglets `général`, `validés`, `annulés`.
- BF-HISTC-02 Filtrer par période/statut.
- BF-HISTC-03 Ouvrir la modal historique client.
- BF-HISTC-04 Conserver la lisibilité des cartes (desktop/mobile).

## 6.9 Historique RDV responsable (`historique_rdv_resp`)
- BF-HISTR-01 Rechercher et filtrer multi-commerciaux.
- BF-HISTR-02 Afficher onglets sticky pendant scroll interne du tableau.
- BF-HISTR-03 Maintenir un seul scroll principal utile (pas de double scrollbar parasite).
- BF-HISTR-04 Garantir footer non superposé aux boutons/actions.
- BF-HISTR-05 Ouvrir modal historique client avec UI harmonisée.
- BF-HISTR-06 Permettre export satisfaction Excel selon filtres.

Critères d'acceptation:
- responsive mobile lisible,
- ergonomie de scroll cohérente.

## 6.10 Dashboard responsable (`dashboard_responsable`)
- BF-DBTR-01 Afficher KPI globaux équipe.
- BF-DBTR-02 Afficher état absence des commerciaux.
- BF-DBTR-03 Afficher graphe satisfaction avec filtres (commercial/période).
- BF-DBTR-04 Offrir navigation vers modules responsables:
  - profils commerciaux,
  - fichier clients,
  - historique RDV,
  - objectifs annuels.

## 6.11 Profils commerciaux
- BF-PROF-01 Lister les profils commerciaux.
- BF-PROF-02 Indiquer l'état absent/actif.
- BF-PROF-03 Ajouter un nouveau commercial via modal:
  - nom/prénom/email/mot de passe,
  - confirmation mot de passe,
  - téléphone optionnel.
- BF-PROF-04 Ouvrir la fiche détaillée d'un commercial.

## 6.12 Satisfaction B2B
- BF-SAT-01 Ouvrir le formulaire de satisfaction lié au RDV.
- BF-SAT-02 Enregistrer les réponses et la moyenne.
- BF-SAT-03 Générer/consulter un PDF de questionnaire.
- BF-SAT-04 Afficher le bouton PDF dans les listes quand disponible.
- BF-SAT-05 Exporter les données de satisfaction en Excel (responsable/admin).

Critères d'acceptation:
- bouton PDF visible uniquement si document existe,
- export conforme aux filtres actifs.

## 6.13 Pages légales et cookies
- BF-LGL-01 Rendre accessibles les pages Mentions légales et Politique de confidentialité.
- BF-LGL-02 Afficher une bannière informative sur cookies techniques uniquement.
- BF-LGL-03 Utiliser un bouton d'acquittement type `Compris` (pas de consentement marketing).

## 6.14 APIs métier
- BF-API-01 Fournir les APIs nécessaires au dashboard et aux modales.
- BF-API-02 APIs principales:
  - `api/rdvs-by-date`,
  - `api/map-tournee`,
  - `api/route-optimisee/<date>`,
  - `api/routing-provider-status/?probe=1`,
  - `api/client-details/uuid/<uuid>`,
  - `update-client/uuid/<uuid>`,
  - `api/insee/siret/<siret>`,
  - endpoints historiques/statistiques,
  - `healthz`.
- BF-API-03 Réponses JSON cohérentes (succès/erreur).

## 7. Exigences de droits d'accès (fonctionnelles)
- ACC-01 Commercial: accès strict à ses clients, ses RDV, ses tournées.
- ACC-02 Responsable/admin: accès multi-commerciaux selon écran.
- ACC-03 Aucune modification d'objet hors périmètre autorisé.
- ACC-04 Les actions refusées doivent renvoyer un message explicite.

## 8. Exigences UX fonctionnelles
- UX-01 Interface cohérente entre modules (styles, boutons, toasts, modales).
- UX-02 Responsive obligatoire sur desktop et mobile (390x844 min).
- UX-03 Aucun élément critique ne doit être masqué (footer, boutons, cartes, modales).
- UX-04 Les feedbacks utilisateurs doivent être immédiats et actionnables.

## 9. Critères d'acceptation globaux
Le besoin fonctionnel est considéré conforme si:
1. les parcours commerciaux bout-en-bout sont réalisables sans blocage,
2. les parcours responsables bout-en-bout sont réalisables sans blocage,
3. les règles métier RDV/clients/objectifs/satisfaction sont respectées,
4. les contrôles d'accès empêchent les actions hors périmètre,
5. les retours UI (toasts/modales/messages) sont cohérents et compréhensibles,
6. les données créées/modifiées sont correctement restituées dans les vues concernées.

## 10. Dépendances fonctionnelles externes
- API INSEE (enrichissement SIRET, best effort).
- Google Maps APIs (routing, selon configuration).
- Services email (reset password/notifications selon backend).

## 11. Backlog fonctionnel recommandé
- BKL-01 Finaliser la suppression des flux legacy `client_id` restants.
- BKL-02 Renforcer les confirmations custom homogènes (remplacer natif partout).
- BKL-03 Ajouter une vue audit consultable des logs d'activité.
- BKL-04 Ajouter reporting responsable multi-périodes avancé.
