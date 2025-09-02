from textblob import TextBlob
import re
from datetime import date, time, timedelta
from .models import Rendezvous, Commercial, FrontClient, Adresse
import math

def analyze_sentiment_french(text):
    """
    Analyse le sentiment d'un texte en français.
    Retourne un score entre -1 (très négatif) et 1 (très positif).
    """
    if not text or not text.strip():
        return 0.0
    
    # Nettoyage du texte
    cleaned_text = re.sub(r'[^\w\s]', '', text.lower())
    
    # Dictionnaire de mots français avec scores d'intensité
    french_positive_words = {
        # Très positif (score: 0.8-1.0)
        'excellent': 0.9, 'parfait': 0.9, 'génial': 0.9, 'fantastique': 0.9,
        'merveilleux': 0.9, 'extraordinaire': 0.9, 'exceptionnel': 0.9,
        'recommandé': 0.8, 'recommandation': 0.8, 'vivement': 0.8,
        
        # Positif (score: 0.5-0.7)
        'satisfait': 0.6, 'content': 0.6, 'heureux': 0.6, 'ravi': 0.6,
        'enthousiaste': 0.6, 'positif': 0.6, 'bon': 0.5, 'bien': 0.5,
        'correct': 0.5, 'acceptable': 0.5, 'convenable': 0.5,
        
        # Neutre-positif (score: 0.2-0.4)
        'rapide': 0.3, 'efficace': 0.3, 'professionnel': 0.3,
        'qualité': 0.3, 'fiable': 0.3, 'sérieux': 0.3, 'réactif': 0.3,
        'disponible': 0.3, 'compréhensif': 0.3, 'flexible': 0.3,
        'économique': 0.2, 'compétitif': 0.2, 'abordable': 0.2,
        'intéressant': 0.2, 'conseillé': 0.2, 'suggéré': 0.2
    }
    
    french_negative_words = {
        # Très négatif (score: -0.8 à -1.0)
        'Pas terrible': -0.9, 'horrible': -0.9, 'catastrophique': -0.9,
        'désastreux': -0.9, 'épouvantable': -0.9, 'abominable': -0.9,
        'déconseillé': -0.8, 'A évité': -0.8, 'rejeté': -0.8,
        
        # Négatif (score: -0.5 à -0.7)
        'insatisfait': -0.6, 'mécontent': -0.6, 'fâché': -0.6,
        'énervé': -0.6, 'frustré': -0.6, 'déçu': -0.6, 'mauvais': -0.5,
        'nul': -0.5, 'problème': -0.5, 'difficile': -0.5,
        
        # Neutre-négatif (score: -0.2 à -0.4)
        'compliqué': -0.3, 'complexe': -0.3, 'confus': -0.3,
        'embrouillé': -0.3, 'lent': -0.3, 'inefficace': -0.3,
        'amateur': -0.3, 'peu fiable': -0.3, 'douteux': -0.3,
        'indisponible': -0.2, 'incompréhensif': -0.2, 'rigide': -0.2,
        'cher': -0.2, 'coûteux': -0.2, 'onéreux': -0.2
    }
    
    # Expressions négatives françaises
    negative_phrases = [
        'pas terrible', 'pas bon', 'pas satisfait', 'ne recommande pas',
        'à améliorer', 'problème de', 'déçu de', 'mécontent de',
        'pas terrible', 'pas terrible', 'pas terrible'  # Répété pour insister
    ]
    
    # Analyse des expressions négatives
    negative_phrase_score = 0
    for phrase in negative_phrases:
        if phrase in text.lower():
            negative_phrase_score -= 0.3  # Score négatif pour chaque expression
    
    # Analyse avec TextBlob (traduction automatique en anglais)
    try:
        blob = TextBlob(cleaned_text)
        # TextBlob fonctionne mieux en anglais, on traduit
        english_text = str(blob.translate(to='en'))
        english_blob = TextBlob(english_text)
        textblob_score = english_blob.sentiment.polarity
    except:
        textblob_score = 0.0
    
    # Analyse basée sur les mots français avec scores d'intensité
    words = cleaned_text.split()
    french_score = 0.0
    word_count = 0
    
    for word in words:
        if word in french_positive_words:
            french_score += french_positive_words[word]
            word_count += 1
        elif word in french_negative_words:
            french_score += french_negative_words[word]
            word_count += 1
    
    # Normalisation du score français
    if word_count > 0:
        french_score = french_score / word_count
    else:
        french_score = 0.0
    
    # Ajout du score des expressions négatives
    french_score += negative_phrase_score
    
    # Combinaison des scores (TextBlob + analyse française)
    final_score = (textblob_score + french_score) / 2
    
    # Normalisation entre -1 et 1
    return max(-1.0, min(1.0, final_score))

def calculate_comprehensive_satisfaction_score(satisfaction_obj):
    """
    Calcule un score de satisfaction sur 10 en prenant en compte toutes les questions SAUF 11, 16, 17, 18, 19.
    Retourne un score entre 0 et 10.
    """
    scores = []
    
    # Q1: Satisfaction qualité pièces (Oui/Non)
    if satisfaction_obj.satisfaction_qualite_pieces:
        score = 10.0 if satisfaction_obj.satisfaction_qualite_pieces == 'oui' else 0.0
        scores.append(score)
    
        # Q2: Note qualité pièces (1-5)
    if satisfaction_obj.note_qualite_pieces:
        score = (satisfaction_obj.note_qualite_pieces * 2) if satisfaction_obj.note_qualite_pieces <= 5 else satisfaction_obj.note_qualite_pieces
        scores.append(score)
    
    # Q3: Problème qualité pièce (Oui/Non) - INVERSE
    if satisfaction_obj.probleme_qualite_piece:
        score = 0.0 if satisfaction_obj.probleme_qualite_piece == 'oui' else 10.0
        scores.append(score)
    
    # Q4: Type problème qualité (texte)
    if satisfaction_obj.type_probleme_qualite_piece:
        sentiment = analyze_sentiment_french(satisfaction_obj.type_probleme_qualite_piece)
        score = (sentiment + 1) * 5  # -1,1 -> 0,10
        scores.append(score)
    
    # Q5: Satisfaction délai livraison (Oui/Non)
    if satisfaction_obj.satisfaction_delai_livraison:
        score = 10.0 if satisfaction_obj.satisfaction_delai_livraison == 'oui' else 0.0
        scores.append(score)
    
    # Q6: Délai livraison moyen (choix)
    if satisfaction_obj.delai_livraison_moyen:
        delai_scores = {
            'moins_24h': 10.0,
            '1_2j': 8.0,
            '3_4j': 6.0,
            'plus_5j': 2.0
        }
        score = delai_scores.get(satisfaction_obj.delai_livraison_moyen, 5.0)
        scores.append(score)
    
    # Q7: Délai livraison idéal (choix)
    if satisfaction_obj.delai_livraison_ideal:
        delai_ideal_scores = {
            'moins_24h': 10.0,
            '1_2j': 8.0,
            '3_4j': 6.0,
            'autre': 5.0
        }
        score = delai_ideal_scores.get(satisfaction_obj.delai_livraison_ideal, 5.0)
        scores.append(score)
    
    # Q8: Délai idéal autre (texte)
    if satisfaction_obj.delai_livraison_ideal_autre:
        sentiment = analyze_sentiment_french(satisfaction_obj.delai_livraison_ideal_autre)
        score = (sentiment + 1) * 5  # -1,1 -> 0,10
        scores.append(score)
    
    # Q9: Recours SAV (Oui/Non) - NEUTRE (peut être positif ou négatif)
    # On ne l'inclut pas dans le score global car c'est neutre
    
    # Q10: Note SAV (1-5)
    if satisfaction_obj.note_sav:
        score = (satisfaction_obj.note_sav * 2) if satisfaction_obj.note_sav <= 5 else satisfaction_obj.note_sav
        scores.append(score)
    
    # Q11: Pièces non disponibles (texte)
    # EXCLU du calcul
    
    # Q12: Satisfaction expérience Rubio (Oui/Non)
    if satisfaction_obj.satisfaction_experience_rubio:
        score = 10.0 if satisfaction_obj.satisfaction_experience_rubio == 'oui' else 0.0
        scores.append(score)
    
    # Q13: Personnel joignable (Oui/Non)
    if satisfaction_obj.personnel_joignable:
        score = 10.0 if satisfaction_obj.personnel_joignable == 'oui' else 0.0
        scores.append(score)
    
    # Q14: Note accueil (1-5)
    if satisfaction_obj.note_accueil:
        score = (satisfaction_obj.note_accueil * 2) if satisfaction_obj.note_accueil <= 5 else satisfaction_obj.note_accueil
        scores.append(score)
    
    # Q15: Commande simple (Oui/Non)
    if satisfaction_obj.commande_simple:
        score = 10.0 if satisfaction_obj.commande_simple == 'oui' else 0.0
        scores.append(score)
    
    # Q16: Moyen commande (choix)
    # EXCLU du calcul
    
    # Q17: Moyen commande autre (texte)
    # EXCLU du calcul
    
    # Q18: Suggestions (texte)
    # EXCLU du calcul
    
    # Q19: Motivation commande (texte)
    # EXCLU du calcul
    
    # Q20: Note recommandation (1-10)
    if satisfaction_obj.note_recommandation:
        score = satisfaction_obj.note_recommandation  # Déjà sur 10
        scores.append(score)
    
    # Calcul de la moyenne sur 10
    if scores:
        final_score = sum(scores) / len(scores)
        return round(final_score, 2)
    else:
        return 5.0  # Score neutre si aucune réponse

def calculate_hybrid_satisfaction_score(satisfaction_obj):
    """
    Calcule un score hybride combinant les notes numériques et l'analyse textuelle.
    Retourne un score entre 0 et 100.
    """
    # Score basé sur les notes numériques (actuel)
    numeric_score = 0
    numeric_count = 0
    
    if satisfaction_obj.note_qualite_pieces:
        numeric_score += satisfaction_obj.note_qualite_pieces * 20  # 1-5 -> 0-100
        numeric_count += 1
    
    if satisfaction_obj.note_sav:
        numeric_score += satisfaction_obj.note_sav * 20  # 1-5 -> 0-100
        numeric_count += 1
    
    if satisfaction_obj.note_accueil:
        numeric_score += satisfaction_obj.note_accueil * 20  # 1-5 -> 0-100
        numeric_count += 1
    
    if satisfaction_obj.note_recommandation:
        numeric_score += satisfaction_obj.note_recommandation * 10  # 1-10 -> 0-100
        numeric_count += 1
    
    # Score numérique final
    if numeric_count > 0:
        final_numeric_score = numeric_score / numeric_count
    else:
        final_numeric_score = 50.0
    
    # Score basé sur l'analyse textuelle
    text_score = calculate_text_satisfaction_score(satisfaction_obj)
    
    # Score hybride : 70% numérique + 30% textuel
    hybrid_score = (final_numeric_score * 0.7) + (text_score * 0.3)
    
    return round(hybrid_score, 2) 

def calculate_text_satisfaction_score(satisfaction_obj) -> float:
    """
    Calcule un score textuel 0-100 à partir des champs libres de SatisfactionB2B
    en s’appuyant sur analyze_sentiment_french (score -1..1).
    On agrège les champs textuels disponibles et on moyenne.
    """
    text_fields = []
    # Collecter les champs potentiels si présents sur l’objet
    for attr in [
        'commentaire_general', 'remarques', 'points_amelioration', 'points_forts',
        'avis_libre', 'suggestions', 'commentaires'
    ]:
        if hasattr(satisfaction_obj, attr):
            val = getattr(satisfaction_obj, attr) or ''
            if isinstance(val, str) and val.strip():
                text_fields.append(val)

    if not text_fields:
        return 50.0  # neutre si pas de texte

    scores = []
    for txt in text_fields:
        s = analyze_sentiment_french(txt)  # -1..1
        # Convertir en 0..100
        scores.append((s + 1.0) * 50.0)

    return sum(scores) / len(scores)

def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371  # Rayon de la Terre en km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c * 1000  # en mètres


def is_jour_ferie_france(d):
    # Jours fériés fixes
    jours_feries = [
        date(d.year, 1, 1),   # Jour de l'an
        date(d.year, 5, 1),   # Fête du Travail
        date(d.year, 5, 8),   # Victoire 1945
        date(d.year, 7, 14),  # Fête nationale
        date(d.year, 8, 15),  # Assomption
        date(d.year, 11, 1),  # Toussaint
        date(d.year, 11, 11), # Armistice
        date(d.year, 12, 25), # Noël
    ]
    # Calcul de Pâques (algorithme de Meeus/Jones/Butcher)
    a = d.year % 19
    b = d.year // 100
    c = d.year % 100
    d1 = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d1 - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois_paques = (h + l - 7 * m + 114) // 31
    jour_paques = ((h + l - 7 * m + 114) % 31) + 1
    paques = date(d.year, mois_paques, jour_paques)
    # Jours fériés mobiles
    lundi_paques = paques + timedelta(days=1)
    ascension = paques + timedelta(days=39)
    pentecote = paques + timedelta(days=50)
    jours_feries += [lundi_paques, ascension, pentecote]
    return d in jours_feries


def generer_rendezvous_automatiques(date_cible=None):
    """
    Génère 7 RDV optimisés pour chaque commercial actif pour la date donnée (ou aujourd'hui).
    Ne crée rien le week-end ou les jours fériés. Retourne le nombre de RDV créés.
    """
    if date_cible is None:
        date_cible = date.today()
    if date_cible.weekday() >= 5 or is_jour_ferie_france(date_cible):
        return 0  # Ne rien faire le week-end ou les jours fériés

    creneaux = [time(8,0), time(8,35), time(9,10), time(9,45), time(10,20), time(10,55), time(11,30)]
    rdv_crees = 0
    # Point de départ générique (à adapter par commercial si besoin)
    point_depart = [-0.3807202, 43.3482402]  # Lons

    commerciaux = Commercial.objects.filter(role='commercial')
    for commercial_obj in commerciaux:
        # --- NOUVEAU : Supprimer TOUS les RDV existants de la date cible ---
        Rendezvous.objects.filter(
            commercial=commercial_obj,
            date_rdv=date_cible
        ).delete()
        
        # Récupérer les clients de ce commercial (logique simple qui marche)
        clients = FrontClient.objects.filter(commercial=commercial_obj.commercial)
        
        # NOUVEAU : Récupérer TOUS les clients du commercial (pas de limite de 50)
        points_a_visiter = []
        for client in clients:
            for adresse in client.adresses.all():
                if adresse.latitude and adresse.longitude:
                    points_a_visiter.append({
                        'client_id': client.id,
                        'client_nom': client.rs_nom,
                        'adresse': adresse.adresse,
                        'coords': [float(adresse.longitude), float(adresse.latitude)]
                    })
        
        # NOUVEAU : Système de rotation - exclure les clients visités récemment (7 derniers jours)
        date_limite = date_cible - timedelta(days=7)
        clients_recemment_visites = set(
            Rendezvous.objects.filter(
                commercial=commercial_obj,
                date_rdv__gte=date_limite,
                statut_rdv__in=['valide', 'a_venir', 'en_retard']
            ).values_list('client_id', flat=True)
        )
        
        # Filtrer les clients non visités récemment
        points_disponibles = [p for p in points_a_visiter if p['client_id'] not in clients_recemment_visites]
        
        # Si pas assez de clients disponibles, réduire la période d'exclusion
        if len(points_disponibles) < 7:
            date_limite = date_cible - timedelta(days=3)
            clients_recemment_visites = set(
                Rendezvous.objects.filter(
                    commercial=commercial_obj,
                    date_rdv__gte=date_limite,
                    statut_rdv__in=['valide', 'a_venir', 'en_retard']
                ).values_list('client_id', flat=True)
            )
            points_disponibles = [p for p in points_a_visiter if p['client_id'] not in clients_recemment_visites]
        
        # Si toujours pas assez, prendre tous les clients disponibles
        if len(points_disponibles) < 7:
            points_disponibles = points_a_visiter
        
        # Point de départ = dernier client visité la veille
        hier = date_cible - timedelta(days=1)
        dernier_rdv = Rendezvous.objects.filter(
            commercial=commercial_obj,
            date_rdv=hier
        ).order_by('-heure_rdv').first()
        if dernier_rdv and dernier_rdv.client:
            adresse_depart = dernier_rdv.client.adresses.filter(latitude__isnull=False, longitude__isnull=False).first()
            if adresse_depart:
                lon0 = float(adresse_depart.longitude)
                lat0 = float(adresse_depart.latitude)
            else:
                lon0, lat0 = point_depart
        else:
            lon0, lat0 = point_depart

        # Calculer les distances et trier par proximité
        for p in points_disponibles:
            lon, lat = p['coords']
            p['distance_from_start'] = haversine_distance(lon0, lat0, lon, lat)
        
        # NOUVEAU : Ajouter un facteur aléatoire pour éviter la répétition exacte
        import random
        random.shuffle(points_disponibles)
        points_disponibles.sort(key=lambda x: x['distance_from_start'])
        
        # Prendre les 7 premiers clients disponibles
        tournee = points_disponibles[:7]
        
        for idx, rdv in enumerate(tournee):
            if idx >= len(creneaux):
                break
            client_obj = FrontClient.objects.filter(id=rdv['client_id']).first()
            if not client_obj:
                continue
            # Plus besoin de vérifier l'existence car on a tout supprimé
            Rendezvous.objects.create(
                client=client_obj,
                commercial=commercial_obj,
                date_rdv=date_cible,
                heure_rdv=creneaux[idx],
                objet="",
                statut_rdv='a_venir',
                rs_nom=client_obj.rs_nom
            )
            rdv_crees += 1
    return rdv_crees 

def generer_rendezvous_simples(date_cible=None, commercial=None):
    """
    Génère 7 RDV simples pour un commercial donné à une date donnée.
    Version simplifiée sans optimisation géographique.
    """
    if date_cible is None:
        date_cible = date.today()
    
    if date_cible.weekday() >= 5 or is_jour_ferie_france(date_cible):
        return 0  # Ne rien faire le week-end ou les jours fériés

    creneaux = [time(8,0), time(8,35), time(9,10), time(9,45), time(10,20), time(10,55), time(11,30)]
    rdv_crees = 0
    
    # Si un commercial spécifique est fourni, on ne traite que celui-ci
    if commercial:
        commerciaux = [commercial]
    else:
        commerciaux = Commercial.objects.filter(role='commercial')

    for commercial_obj in commerciaux:
        # Objectif: 7 RDV par JOUR et par commercial via la génération automatique.
        # On calcule la capacité restante pour la date cible uniquement.
        rdv_existants_jour = Rendezvous.objects.filter(
            commercial=commercial_obj,
            date_rdv=date_cible,
            statut_rdv='a_venir'
        ).count()
        capacite_restante = max(0, 7 - rdv_existants_jour)
        if capacite_restante == 0:
            # Déjà 7 RDV ce jour-là: ne rien ajouter pour ce commercial
            continue
        
        # Récupérer TOUS les clients de ce commercial
        clients_commercial = FrontClient.objects.filter(commercial_id=commercial_obj.id)
        
        if not clients_commercial.exists():
            continue
        
        # NOUVEAU : Système de rotation - exclure les clients visités récemment (7 derniers jours)
        date_limite = date_cible - timedelta(days=7)
        clients_recemment_visites = set(
            Rendezvous.objects.filter(
                commercial=commercial_obj,
                date_rdv__gte=date_limite,
                statut_rdv__in=['valide', 'a_venir', 'en_retard']
            ).values_list('client_id', flat=True)
        )
        
        # Filtrer les clients non visités récemment
        clients_disponibles = [c for c in clients_commercial if c.id not in clients_recemment_visites]
        
        # Si pas assez de clients disponibles, réduire la période d'exclusion
        if len(clients_disponibles) < 7:
            date_limite = date_cible - timedelta(days=3)
            clients_recemment_visites = set(
                Rendezvous.objects.filter(
                    commercial=commercial_obj,
                    date_rdv__gte=date_limite,
                    statut_rdv__in=['valide', 'a_venir', 'en_retard']
                ).values_list('client_id', flat=True)
            )
            clients_disponibles = [c for c in clients_commercial if c.id not in clients_recemment_visites]
        
        # Si toujours pas assez, prendre tous les clients disponibles
        if len(clients_disponibles) < 7:
            clients_disponibles = list(clients_commercial)
        
        # NOUVEAU : Ajouter un facteur aléatoire pour éviter la répétition exacte
        import random
        random.shuffle(clients_disponibles)
        
        # Prendre au plus la capacité restante (<= 7 - déjà planifiés ce jour)
        clients_selectionnes = clients_disponibles[:min(7, capacite_restante)]
        
        # Créer les RDV
        for idx, client_obj in enumerate(clients_selectionnes):
            if idx >= len(creneaux):
                break
                
            # Vérifier qu'il n'y a pas déjà un RDV pour ce client à cette date
            rdv_existe = Rendezvous.objects.filter(
                client=client_obj,
                commercial=commercial_obj,
                date_rdv=date_cible
            ).exists()
            
            if not rdv_existe and capacite_restante > 0:
                Rendezvous.objects.create(
                    client=client_obj,
                    commercial=commercial_obj,
                    date_rdv=date_cible,
                    heure_rdv=creneaux[idx],
                    objet="",
                    statut_rdv='a_venir',
                    rs_nom=client_obj.rs_nom
                )
                rdv_crees += 1
                capacite_restante -= 1
    
    return rdv_crees 