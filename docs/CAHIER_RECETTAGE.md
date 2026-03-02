# Cahier de Recettage - CRM Visites

Version: 1.0  
Projet: `crm_visites`  
Environnement cible: `preview/dev` puis `prod`  
Date: 2026-02-27

## 1. Objectif
Valider de bout en bout le CRM (commerciaux + responsables + APIs) sur:
- conformité fonctionnelle,
- non-régression,
- sécurité applicative,
- UX responsive (desktop/mobile),
- cohérence des droits d'accès.

## 2. Périmètre
Couvert:
- Authentification / session / reset password
- Dashboard commercial (`dashboard_test`)
- Dashboard responsable (`dashboard_responsable`)
- Gestion clients (`client_file`, `new_client`, update client)
- Gestion RDV (`add_rdv`, statuts, commentaires/pin)
- Historiques (`historique_rdv`, `historique_rdv_resp`)
- Objectifs annuels (`objectif_annuel`)
- Satisfaction B2B / PDF / export Excel
- APIs métier (map tournée, routing, insee, stats, recherches)
- Pages légales + bannière cookies

Hors périmètre:
- tests de charge lourde (perf volumétrique avancée),
- pentest externe.

## 3. Pré-requis de recette
1. Base à jour (`migrate` OK).
2. Comptes disponibles:
   - 1 commercial actif,
   - 1 commercial absent,
   - 1 responsable/admin.
3. Jeu de données:
   - clients avec et sans email/téléphone,
   - clients avec UUID,
   - RDV `a_venir`, `valide`, `annule`, en retard.
4. Variables d'env configurées si test INSEE/Google:
   - `GOOGLE_MAPS_API_KEY` (si test provider Google),
   - `INSEE_*` (si test auto-recherche SIRET).
5. Navigateurs:
   - Chrome/Edge desktop,
   - device mobile (iPhone 12 Pro viewport 390x844 min).

## 4. Stratégie de test
- Manuel fonctionnel (UI + parcours métiers).
- Vérification API via DevTools Network / `fetch`.
- Tests auto Django:
  - `python manage.py test front -v 2`
  - ou via Docker: `docker compose ... exec -T web_preview python manage.py test front -v 2`
- Check système:
  - `python manage.py check`

## 5. Matrice de traçabilité (macro)
- AUTH: TC-AUTH-*
- SESSION/SECU: TC-SECU-*
- DASHBOARD COMMERCIAL: TC-DBTC-*
- DASHBOARD RESPONSABLE: TC-DBTR-*
- CLIENTS: TC-CL-*
- RDV: TC-RDV-*
- COMMENTAIRES/PIN: TC-PIN-*
- OBJECTIFS: TC-OBJ-*
- HISTORIQUES: TC-HIST-*
- SATISFACTION/PDF/EXPORT: TC-SAT-*
- API: TC-API-*
- RESPONSIVE/UI: TC-UI-*
- LEGAL/COOKIE: TC-LGL-*

## 6. Cas de tests détaillés

## 6.1 AUTH / SESSION

### TC-AUTH-001 Login commercial valide
Précondition: compte commercial actif.  
Étapes:
1. Ouvrir `/login/`.
2. Saisir email/mot de passe valides.
Attendu:
- redirection vers `dashboard_test`,
- session créée,
- menu utilisateur affiché.

### TC-AUTH-002 Login responsable valide
Précondition: compte responsable/admin actif.  
Étapes: login avec compte responsable.  
Attendu:
- redirection `dashboard_responsable`.

### TC-AUTH-003 Login invalide
Étapes: mauvais mot de passe.  
Attendu:
- message d'erreur sans fuite d'info sensible,
- pas de session authentifiée.

### TC-AUTH-004 Logout
Étapes: cliquer déconnexion.  
Attendu:
- retour page login,
- endpoints protégés renvoient 302/403 sans session.

### TC-SECU-001 Timeout session + prolongation
Étapes:
1. Simuler inactivité.
2. Vérifier warning timeout.
3. Appeler `extend-session`.
Attendu:
- warning effacé,
- session prolongée.

### TC-AUTH-005 Reset password - email existant
Étapes:
1. `/reset-password/`, saisir email existant.
Attendu:
- message neutre (pas d'énumération explicite),
- pas d'erreur serveur.

### TC-AUTH-006 Reset password - email inexistant
Étapes: saisir email non existant.  
Attendu:
- même message neutre qu'email existant.

### TC-SECU-002 Throttling reset password
Étapes: répéter demandes reset rapidement.  
Attendu:
- limitation active (429 ou message de limitation),
- service reste stable.

## 6.2 DASHBOARD COMMERCIAL (`dashboard_test`)

### TC-DBTC-001 Chargement global
Attendu:
- calendrier visible,
- onglets `Visites à venir/récentes/annulées`,
- carte + panel clients sélectionnés.

### TC-DBTC-002 Récupération RDV par date/statut
Étapes: naviguer mois/jours/onglets.  
Attendu:
- appels `api/rdvs-by-date` en 200,
- badges/jours alimentés correctement.

### TC-DBTC-003 Filtres date
Étapes:
1. Ouvrir modal filtres.
2. Sélectionner plage.
Attendu:
- affichage restreint aux jours concernés,
- reset fonctionne.

### TC-DBTC-004 Map tournée du jour
Étapes:
1. Choisir date >= aujourd'hui.
2. `Charger`.
Attendu:
- markers clients chargés,
- panel sélection cohérent.

### TC-DBTC-005 Blocage date passée map
Étapes: tenter date antérieure aujourd'hui.  
Attendu:
- action bloquée/feedback utilisateur,
- pas de remplacement tournée.

### TC-DBTC-006 Sélection client depuis popup map
Étapes:
1. Ouvrir popup marker.
2. Cliquer `Ajouter`.
Attendu:
- client ajouté au panel,
- bouton popup passe état `Ajouté`.

### TC-DBTC-007 Retrait client + synchro popup
Étapes:
1. Retirer client depuis panel.
Attendu:
- client retiré,
- popup repasse en état ajoutable.

### TC-DBTC-008 Vider sélection
Attendu:
- panel vidé,
- compteur à 0.

### TC-DBTC-009 Valider tournée (confirmation custom)
Étapes:
1. sélectionner N clients,
2. cliquer `Valider la tournée`,
3. confirmer.
Attendu:
- confirmation custom (pas popup navigateur native),
- toast succès,
- map/panel rafraîchis.

### TC-DBTC-010 Toast RDV en retard
Précondition: RDV non validés date < aujourd'hui.  
Attendu:
- toast gradient jaune/orange à connexion,
- compteur exact des RDV en retard.

## 6.3 ADD RDV (`add_rdv`)

### TC-RDV-001 Création RDV standard
Étapes:
1. saisir date/heure/client,
2. valider.
Attendu:
- création en base,
- toast succès,
- redirection différée (~5s) vers `next`.

### TC-RDV-002 Champs obligatoires
Étapes: soumettre sans date/heure/client.  
Attendu:
- toast rouge `Veuillez renseigner date, heure et client`.

### TC-RDV-003 Doublon RDV
Précondition: RDV existant même client/commercial/date/heure.  
Attendu:
- toast rouge `Un rendez-vous existe déjà...`,
- pas de création.

### TC-RDV-004 Objet/commentaire persistés
Étapes:
1. créer RDV avec objet + note.
2. ouvrir fiche client du RDV.
Attendu:
- objet/commentaire visibles.

### TC-RDV-005 Depuis dashboard commercial
Étapes: menu `+` -> `Ajouter un RDV`.  
Attendu:
- ouverture add_rdv,
- retour `next` correct vers dashboard.

### TC-RDV-006 Depuis objectif annuel (responsable)
Étapes: cliquer `Planifier RDV` sur client.  
Attendu:
- `client_uuid` dans URL,
- client prérempli (sans `None`),
- commercial auto-sélectionné et verrouillé.

### TC-RDV-007 Compat legacy
Étapes: ouvrir URL `add-rdv/?client_id=...`.  
Attendu:
- préremplissage fonctionne encore (fallback).

### TC-RDV-008 Dry-run création
Étapes: soumettre avec `dry_run=1`.  
Attendu:
- réponse JSON simulation,
- aucune écriture DB.

### TC-RDV-009 Absence commerciale
Précondition: commercial absent.  
Attendu:
- création bloquée,
- message explicite.

## 6.4 STATUTS RDV / COMMENTAIRES / PIN

### TC-PIN-001 Valider RDV
Attendu:
- statut `valide`,
- date_statut renseignée,
- counters mis à jour.

### TC-PIN-002 Annuler RDV
Attendu:
- statut `annule`,
- counters mis à jour.

### TC-PIN-003 Épingler commentaire immédiat
Étapes: bouton pin en modal client.  
Attendu:
- commentaire épinglé sans étape inutile.

### TC-PIN-004 Désépingler
Attendu:
- retrait effectif du pin.

### TC-SECU-003 Rate-limit pin/unpin
Étapes: spam pin/unpin.  
Attendu:
- limitation active (pas d'abus).

### TC-PIN-005 Affichage style post-it
Attendu:
- rendu visuel post-it + action suppression.

## 6.5 CLIENTS / NEW CLIENT / CLIENT FILE

### TC-CL-001 Liste clients
Attendu:
- pagination,
- recherche,
- filtres raison/adresse/cp/ville/commercial.

### TC-CL-002 Modal client
Attendu:
- header harmonisé,
- croix fermeture avec hover conforme,
- boutons actions cohérents.

### TC-CL-003 Edition client
Étapes: modifier + enregistrer.  
Attendu:
- update en base,
- feedback utilisateur.

### TC-CL-004 Ajout client manuel
Attendu:
- validations (SIRET/Luhn),
- auto-clean chiffres,
- messages dynamiques,
- bordures invalid/valid.

### TC-CL-005 SIRET API INSEE best effort
Attendu:
- si succès: autofill,
- si échec/404: message discret non bloquant,
- création client reste possible.

### TC-CL-006 Import Excel clients
Attendu:
- import valide,
- gestion erreur format/fichier.

### TC-CL-007 Bouton retour
Attendu:
- style homogène (hover fill rouge),
- pas de chevauchement mobile.

## 6.6 OBJECTIFS ANNUELS

### TC-OBJ-001 Accès commercial
Attendu:
- voit ses objectifs uniquement.

### TC-OBJ-002 Accès responsable
Attendu:
- menu `Objectifs annuels` disponible,
- accès page OK.

### TC-OBJ-003 Sélecteur commercial (responsable)
Attendu:
- changement commercial met à jour KPIs/table,
- année conservée.

### TC-OBJ-004 Planifier RDV depuis client objectif
Attendu:
- `next` conserve contexte (`year` + `commercial_id`),
- retour correct après création.

## 6.7 HISTORIQUES

### TC-HIST-001 Historique commercial
Attendu:
- onglets opérationnels,
- filtres période/statut,
- cartes non coupées mobile.

### TC-HIST-002 Historique responsable
Attendu:
- barre recherche + bouton filtre alignés,
- onglets sticky pendant scroll interne,
- scroll principal unique (pas de double inutile),
- footer non superposé aux boutons.

### TC-HIST-003 Modal historique client
Attendu:
- style harmonisé,
- croix fermeture fonctionnelle + hover.

### TC-HIST-004 Badge statut couleurs
Attendu:
- vert/rouge contrastés, lisibles.

## 6.8 SATISFACTION / PDF / EXPORT

### TC-SAT-001 Ouvrir formulaire satisfaction
Attendu:
- nouvel onglet ouvert sans faux toast “popup bloquée” si ouverture réussie.

### TC-SAT-002 Présence PDF
Attendu:
- lien/bouton PDF visible quand questionnaire existe,
- style cohérent (bouton rouge même hauteur que `Ouvrir`).

### TC-SAT-003 Téléchargement PDF
Attendu:
- document téléchargeable,
- droits d'accès respectés.

### TC-SAT-004 Export Excel responsable
Attendu:
- fichier généré,
- contenu cohérent avec filtres.

## 6.9 RESPONSABLE - PROFILS COMMERCIAUX / FICHE COMMERCIAL

### TC-DBTR-001 Liste profils commerciaux
Attendu:
- cartes présentes,
- badge absent,
- bouton `+` visible (responsable uniquement).

### TC-DBTR-002 Ajout commercial via modal
Attendu:
- champs obligatoires OK,
- confirmation mot de passe,
- téléphone facultatif.

### TC-DBTR-003 Fiche commercial scroll
Attendu:
- pas de scroll horizontal parasite,
- pas de scroll vertical “vide”.

## 6.10 API / INTÉGRATION

### TC-API-001 `api/routing-provider-status/?probe=1`
Attendu:
- JSON `ok:true`,
- `probe:'ok'` si provider joignable.

### TC-API-002 `api/map-tournee`
Attendu:
- 200,
- clients + geometry conformes.

### TC-API-003 `api/route-optimisee/<date>`
Attendu:
- mode provider cohérent (`GOOGLE`/fallback),
- ordre optimisé non vide.

### TC-API-004 `api/client-details/uuid/<uuid>`
Attendu:
- 200 si autorisé, 403 sinon.

### TC-API-005 `update-client/uuid/<uuid>`
Attendu:
- update OK,
- refus si non autorisé.

### TC-API-006 `api/insee/siret/<siret>`
Attendu:
- 200/404/429 gérés proprement côté UI.

### TC-API-007 `api/clients-by-commercial`
Attendu:
- responsable: accès paramétrable,
- commercial: restreint à soi.

### TC-API-008 Santé
Endpoint `healthz` répond 200.

## 6.11 SÉCURITÉ APPLICATIVE

### TC-SECU-004 CSRF
Attendu:
- endpoints sensibles protégés CSRF (hors exceptions justifiées).

### TC-SECU-005 Contrôles d'accès objet
Attendu:
- impossible d'accéder/modifier un client/RDV hors périmètre commercial.

### TC-SECU-006 Aucune fuite stacktrace en prod
Attendu:
- messages erreurs user-friendly.

### TC-SECU-007 Headers sécurité
Attendu:
- HSTS/secure cookies activés en prod selon settings.

### TC-SECU-008 Cookies
Attendu:
- bannière informative “cookies techniques uniquement”,
- bouton “Compris”.

## 6.12 RESPONSIVE / UI / UX

### TC-UI-001 Desktop 1366x768
Attendu:
- aucune coupure container critique.

### TC-UI-002 Mobile 390x844
Attendu:
- dashboards lisibles,
- modales scrollables,
- pas de superposition footer/boutons.

### TC-UI-003 Cohérence composants
Attendu:
- rouges harmonisés,
- boutons hover homogènes,
- croix fermeture cohérentes.

### TC-UI-004 Toasts
Attendu:
- positions non masquantes,
- fermetures fonctionnelles,
- messages corrects (succès/erreur).

## 6.13 LÉGAL

### TC-LGL-001 Mentions légales
Accès page + liens retour selon rôle.

### TC-LGL-002 Politique confidentialité
Contenu lisible mobile/desktop + liens footer.

## 7. Critères de passage GO/NO-GO
GO si:
1. 100% des tests bloquants PASS:
   - AUTH, accès rôle, création RDV, update statut, objectif annuel, historique, export PDF/Excel.
2. 0 erreur 500 sur parcours nominal.
3. 0 fail sécurité critique (accès horizontal, CSRF, reset abuse sans limite).

NO-GO si:
- fail sur droits d'accès,
- perte de données métier,
- régression majeure parcours commercial.

## 8. Journal d'exécution (template)
| ID Test | Statut (PASS/FAIL/BLOCKED) | Environnement | Build/Commit | Preuve (capture/log) | Commentaire |
|---|---|---|---|---|---|
| TC-AUTH-001 |  |  |  |  |  |
| TC-RDV-001 |  |  |  |  |  |
| TC-OBJ-003 |  |  |  |  |  |

## 9. Anomalies (template)
| Bug ID | Sévérité | Cas lié | Description | Étapes de repro | Résultat attendu | Résultat obtenu | Statut |
|---|---|---|---|---|---|---|---|
| BUG-001 | Critique | TC-RDV-001 |  |  |  |  |  |

## 10. Commandes utiles recette
- Check Django:  
`python manage.py check`
- Tests auto (local):  
`python manage.py test front -v 2`
- Tests auto (Docker):  
`docker compose -f docker-compose.yml -f docker-compose.preview.yml exec -T web_preview python manage.py test front -v 2`

## 11. Notes
- Conserver les captures écran des tests UI/mobile.
- Ajouter un tag de version/commit dans chaque PV de recette.
- Toujours tester au moins 1 parcours complet commercial + 1 parcours complet responsable après chaque merge `dev`.
