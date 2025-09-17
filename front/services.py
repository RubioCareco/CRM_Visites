import requests
import time
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
from django.utils import timezone
from datetime import date, datetime, timedelta, time as dtime
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from .models import Adresse, Commercial, Rendezvous, FrontClient, ClientVisitStats


class GeocodingService:
    """Service pour géocoder les adresses avec Nominatim (OpenStreetMap)"""
    
    BASE_URL = "https://nominatim.openstreetmap.org/search"
    
    @classmethod
    def geocode_address(cls, adresse: str, code_postal: str, ville: str) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Géocode une adresse avec logique de fallback
        """
        headers = {
            'User-Agent': 'CRM-Visites/1.0 (https://github.com/your-repo)'
        }
        
        # Essai 1 : Adresse complète
        full_address = f"{adresse}, {code_postal} {ville}, France"
        coords = cls._try_geocode(full_address, headers)
        if coords:
            return coords
        
        # Essai 2 : Sans le nom d'entreprise (prendre après le premier tiret ou espace)
        if ' - ' in adresse:
            clean_address = adresse.split(' - ')[-1].strip()
        elif ' ' in adresse and not adresse[0].isdigit():
            # Si l'adresse ne commence pas par un chiffre, prendre après le premier espace
            parts = adresse.split(' ', 1)
            if len(parts) > 1:
                clean_address = parts[1]
            else:
                clean_address = adresse
        else:
            clean_address = adresse
            
        if clean_address != adresse:
            fallback_address = f"{clean_address}, {code_postal} {ville}, France"
            coords = cls._try_geocode(fallback_address, headers)
            if coords:
                return coords
        
        # Essai 3 : Juste la ville et le code postal
        city_address = f"{code_postal} {ville}, France"
        coords = cls._try_geocode(city_address, headers)
        if coords:
            return coords
        
        return None
    
    @classmethod
    def _try_geocode(cls, address: str, headers: dict) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Essaie de géocoder une adresse
        """
        params = {
            'q': address,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'fr'
        }
        
        try:
            response = requests.get(cls.BASE_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                lat = Decimal(data[0]['lat'])
                lon = Decimal(data[0]['lon'])
                return lat, lon
            
        except Exception as e:
            print(f"Échec géocodage pour {address}: {e}")
        
        return None
    
    @classmethod
    def geocode_all_addresses(cls):
        """
        Géocode toutes les adresses qui n'ont pas encore de coordonnées
        """
        addresses = Adresse.objects.filter(latitude__isnull=True, longitude__isnull=True)
        
        for address in addresses:
            if address.adresse and address.code_postal and address.ville:
                coords = cls.geocode_address(address.adresse, address.code_postal, address.ville)
                
                if coords:
                    address.latitude, address.longitude = coords
                    address.geocode_date = timezone.now()
                    address.save()
                    print(f"Géocodé: {address}")
                else:
                    print(f"Échec géocodage: {address}")
                
                # Pause pour respecter les limites de l'API
                time.sleep(1)


class RouteOptimizationService:
    """Service d'optimisation de trajet avec algorithme Nearest Neighbor"""
    
    @classmethod
    def calculate_distance(cls, lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
        """
        Calcule la distance en km entre deux points (formule de Haversine)
        """
        from math import radians, cos, sin, asin, sqrt
        
        # Conversion en radians
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Différences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Formule de Haversine
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Rayon de la Terre en km
        
        return c * r
    
    @classmethod
    def nearest_neighbor_optimization(cls, commercial: Commercial, date_rdv: str, max_rdv: int = 7) -> List[Rendezvous]:
        """
        Optimise l'ordre des rendez-vous avec l'algorithme Nearest Neighbor
        
        Args:
            commercial: Le commercial concerné
            date_rdv: Date des rendez-vous (YYYY-MM-DD)
            max_rdv: Nombre maximum de rendez-vous à optimiser
            
        Returns:
            Liste des rendez-vous dans l'ordre optimisé
        """
        # Récupération des rendez-vous à venir pour ce commercial à cette date
        rdvs = Rendezvous.objects.filter(
            commercial=commercial,
            date_rdv=date_rdv,
            statut_rdv='a_venir'
        ).order_by('heure_rdv')[:max_rdv]
        
        if not rdvs:
            return []
        
        # Récupération des adresses des clients avec coordonnées
        rdvs_with_coords = []
        for rdv in rdvs:
            if rdv.client:
                # Prendre la première adresse du client
                address = rdv.client.adresses.filter(
                    latitude__isnull=False,
                    longitude__isnull=False
                ).first()
                
                if address:
                    rdvs_with_coords.append({
                        'rdv': rdv,
                        'lat': address.latitude,
                        'lon': address.longitude,
                        'address': address
                    })
        
        if not rdvs_with_coords:
            return [rdv['rdv'] for rdv in rdvs_with_coords]
        
        # Point de départ (domicile du commercial)
        if commercial.latitude_depart and commercial.longitude_depart:
            start_lat = commercial.latitude_depart
            start_lon = commercial.longitude_depart
        else:
            # Si pas de point de départ, utiliser le premier rendez-vous
            start_lat = rdvs_with_coords[0]['lat']
            start_lon = rdvs_with_coords[0]['lon']
        
        # Algorithme Nearest Neighbor
        optimized_route = []
        current_lat, current_lon = start_lat, start_lon
        unvisited = rdvs_with_coords.copy()
        
        while unvisited:
            # Trouver le point le plus proche
            min_distance = float('inf')
            nearest_idx = 0
            
            for i, rdv_data in enumerate(unvisited):
                distance = cls.calculate_distance(
                    current_lat, current_lon,
                    rdv_data['lat'], rdv_data['lon']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = i
            
            # Ajouter le rendez-vous le plus proche à la route
            nearest_rdv = unvisited.pop(nearest_idx)
            optimized_route.append(nearest_rdv['rdv'])
            
            # Mettre à jour la position actuelle
            current_lat = nearest_rdv['lat']
            current_lon = nearest_rdv['lon']
        
        return optimized_route
    
    @classmethod
    def get_optimized_route_for_commercial(cls, commercial: Commercial, date_rdv: str) -> dict:
        """
        Retourne une route optimisée avec les informations de distance
        """
        optimized_rdvs = cls.nearest_neighbor_optimization(commercial, date_rdv)
        
        if not optimized_rdvs:
            return {
                'rdvs': [],
                'total_distance': 0,
                'estimated_time': 0
            }
        
        # Calcul de la distance totale
        total_distance = 0
        current_lat = commercial.latitude_depart or 0
        current_lon = commercial.longitude_depart or 0
        
        route_details = []
        
        for rdv in optimized_rdvs:
            if rdv.client:
                address = rdv.client.adresses.filter(
                    latitude__isnull=False,
                    longitude__isnull=False
                ).first()
                
                if address:
                    distance = cls.calculate_distance(
                        current_lat, current_lon,
                        address.latitude, address.longitude
                    )
                    total_distance += distance
                    
                    route_details.append({
                        'rdv': rdv,
                        'distance_from_previous': distance,
                        'address': address
                    })
                    
                    current_lat = address.latitude
                    current_lon = address.longitude
        
        # Estimation du temps (50 km/h en moyenne)
        estimated_time_hours = total_distance / 50
        estimated_time_minutes = int(estimated_time_hours * 60)
        
        return {
            'rdvs': optimized_rdvs,
            'route_details': route_details,
            'total_distance': round(total_distance, 2),
            'estimated_time_minutes': estimated_time_minutes
        } 


# ============================
# Planification des rendez-vous
# ============================

CLASSEMENT_TO_TARGET_28D: Dict[str, int] = {
    'A': 10,
    'B': 5,
    'C': 1,
    '': 1,  # N/A
    None: 1,
}


def _load_holidays_for_years(country_code: str, years: list[int]) -> set[str]:
    """Charge les jours fériés via python-holidays si dispo, sinon renvoie set()"""
    try:
        import holidays as pyholidays  # type: ignore
    except Exception:
        return set()

    dates: set[str] = set()
    try:
        for y in years:
            try:
                country_class = getattr(pyholidays, country_code)
            except Exception:
                # Mapping simple pour France
                country_class = getattr(pyholidays, 'FR', None)
            if country_class is None:
                continue
            for d in country_class(years=y):
                dates.add(d.strftime('%Y-%m-%d'))
    except Exception:
        return set()
    return dates


def _get_holiday_set() -> set[str]:
    """Construit l'ensemble des jours fériés en ISO-8601 (YYYY-MM-DD)."""
    # Fallback manuel depuis settings.PUBLIC_HOLIDAYS
    manual: set[str] = set(getattr(settings, 'PUBLIC_HOLIDAYS', []) or [])

    # Essayer via python-holidays si des paramètres sont fournis
    country = getattr(settings, 'HOLIDAYS_COUNTRY', None)
    years_csv = getattr(settings, 'HOLIDAYS_YEARS', None)

    if not country or not years_csv:
        return manual

    try:
        years = [int(x.strip()) for x in str(years_csv).split(',') if x.strip()]
    except Exception:
        years = []

    if not years:
        return manual

    lib = _load_holidays_for_years(country, years)
    return lib or manual


def _is_business_day(target_date: date) -> bool:
    # Lundi=0 ... Dimanche=6
    if target_date.weekday() >= 5:
        return False
    # Jours fériés depuis lib holidays si dispo, sinon fallback settings.PUBLIC_HOLIDAYS
    holiday_set = _get_holiday_set()
    return target_date.isoformat() not in holiday_set


def _count_rdv_non_annules_for_commercial_on_date(commercial: Commercial, d: date) -> int:
    return Rendezvous.objects.filter(
        commercial=commercial,
        date_rdv=d
    ).exclude(statut_rdv='annule').count()


def _rdv_exists_for_client_on_date(client: FrontClient, commercial: Commercial, d: date) -> bool:
    return Rendezvous.objects.filter(
        client=client,
        commercial=commercial,
        date_rdv=d
    ).exclude(statut_rdv='annule').exists()


def _get_objectif_annuel(client: FrontClient, commercial: Commercial, annee: int) -> int:
    # Tenter de lire ClientVisitStats; sinon dériver du classement
    stats = ClientVisitStats.objects.filter(client=client, commercial=commercial, annee=annee).first()
    if stats:
        return stats.objectif
    classement = (client.classement_client or '').upper().strip()
    return CLASSEMENT_TO_TARGET_28D.get(classement, 1)


def _get_visites_valides_annee(client: FrontClient, commercial: Commercial, annee: int) -> int:
    return Rendezvous.objects.filter(
        client=client,
        commercial=commercial,
        date_rdv__year=annee,
        statut_rdv='valide'
    ).count()


def _get_already_planned_in_horizon(client: FrontClient, commercial: Commercial, start_d: date, end_d: date) -> int:
    return Rendezvous.objects.filter(
        client=client,
        commercial=commercial,
        date_rdv__gte=start_d,
        date_rdv__lte=end_d
    ).exclude(statut_rdv='annule').count()


def _iter_business_days(start_d: date, end_d: date):
    d = start_d
    while d <= end_d:
        if _is_business_day(d):
            yield d
        d += timedelta(days=1)


def ensure_visits_next_4_weeks(run_date: Optional[date] = None, *, dry_run: bool = False, collect_breakdown: bool = True) -> dict:
    """Complète la planification jusqu'à J+28.

    - Respecte le plafond 7 RDV/jour/commercial
    - Ignore les commerciaux absents
    - Jours ouvrés uniquement, hors fériés (configurable)
    - Créneau matin 09:00
    - Idempotent via get_or_create (pas de doublon)
    - Prend en compte l'objectif annuel par client (reste annuel)

    Returns: statistiques d'exécution
    """
    start = (run_date or timezone.localdate())
    end = start + timedelta(days=28)

    created_count = 0
    skipped_absence = 0
    skipped_quota = 0
    skipped_existing = 0
    skipped_objectif_zero = 0
    per_day: Dict[str, int] = {}
    per_commercial_per_day: Dict[int, Dict[str, int]] = {}

    # Jours de l'horizon
    business_days = list(_iter_business_days(start, end))

    # Les commerciaux actifs (tous pour l'instant)
    for commercial in Commercial.objects.all():
        if commercial.is_absent:
            skipped_absence += 1
            continue

        # Pré-calcul de capacité par jour
        capacity_by_day = {d: max(0, 7 - _count_rdv_non_annules_for_commercial_on_date(commercial, d)) for d in business_days}
        if collect_breakdown and commercial.id not in per_commercial_per_day:
            per_commercial_per_day[commercial.id] = {}

        # Sélection des clients du commercial (par liaison numerique si présente)
        clients_qs = FrontClient.objects.filter(commercial_id=commercial.id, actif=True)
        # Si pas de liaison stricte, on ne prend pas de risque en incluant seulement ceux liés

        # Priorité C > '' > B > A
        def prio_order(c: FrontClient) -> int:
            val = (c.classement_client or '').upper().strip()
            if val == 'C':
                return 0
            if val == '':
                return 1
            if val == 'B':
                return 2
            if val == 'A':
                return 3
            return 4

        clients = sorted(list(clients_qs), key=prio_order)

        for client in clients:
            classement = (client.classement_client or '').upper().strip()
            cible_28 = CLASSEMENT_TO_TARGET_28D.get(classement, 1)

            annee = start.year
            objectif_annuel = _get_objectif_annuel(client, commercial, annee)
            visites_valides = _get_visites_valides_annee(client, commercial, annee)
            reste_annuel = max(0, objectif_annuel - visites_valides)
            if reste_annuel <= 0:
                skipped_objectif_zero += 1
                continue

            cible_28_effective = min(cible_28, reste_annuel)
            deja_planifies = _get_already_planned_in_horizon(client, commercial, start, end)
            manquants = max(0, cible_28_effective - deja_planifies)
            if manquants == 0:
                continue

            for d in business_days:
                if manquants == 0:
                    break
                if capacity_by_day.get(d, 0) <= 0:
                    continue
                if _rdv_exists_for_client_on_date(client, commercial, d):
                    skipped_existing += 1
                    continue

                if dry_run:
                    # Simule la création
                    capacity_by_day[d] -= 1
                    manquants -= 1
                    created_count += 1
                    if collect_breakdown:
                        per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
                        per_commercial_per_day[commercial.id][d.isoformat()] = per_commercial_per_day[commercial.id].get(d.isoformat(), 0) + 1
                    continue

                with transaction.atomic():
                    obj, created = Rendezvous.objects.get_or_create(
                        client=client,
                        commercial=commercial,
                        date_rdv=d,
                        heure_rdv=dtime(hour=9, minute=0),
                        defaults={
                            'statut_rdv': 'a_venir',
                            'objet': 'Visite planifiée automatiquement',
                        }
                    )
                    if created:
                        created_count += 1
                        capacity_by_day[d] -= 1
                        manquants -= 1
                        if collect_breakdown:
                            per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
                            per_commercial_per_day[commercial.id][d.isoformat()] = per_commercial_per_day[commercial.id].get(d.isoformat(), 0) + 1
                    else:
                        skipped_existing += 1

    return {
        'created': created_count,
        'skipped_absent_commercials': skipped_absence,
        'skipped_quota_days': skipped_quota,
        'skipped_existing': skipped_existing,
        'skipped_objectif_zero': skipped_objectif_zero,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'per_day': per_day if collect_breakdown else None,
        'per_commercial_per_day': per_commercial_per_day if collect_breakdown else None,
    }
