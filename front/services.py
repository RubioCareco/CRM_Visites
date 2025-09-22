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
    """Service d'optimisation de trajet avec algorithme Nearest Neighbor.

    Modes de coût (priorité):
    - Mapbox Matrix (durée routière) si MAPBOX_ACCESS_TOKEN défini
    - OpenRouteService Matrix si ORS_API_KEY défini (+ ROUTING_USE_ORS=True)
    - Haversine (vol d'oiseau) en repli
    """

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

    # ==============================
    # OpenRouteService (facultatif)
    # ==============================
    @staticmethod
    def _ors_enabled() -> bool:
        key = getattr(settings, 'ORS_API_KEY', '') or ''
        return bool(key.strip())

    @staticmethod
    def _ors_headers() -> dict:
        return {
            'Authorization': getattr(settings, 'ORS_API_KEY', ''),
            'Content-Type': 'application/json',
        }

    @classmethod
    def _ors_matrix_durations(cls, source: Tuple[float, float], destinations: List[Tuple[float, float]]) -> Optional[List[float]]:
        """Retourne les durées en minutes du point source vers chaque destination via ORS Matrix.
        source/destinations: (lat, lon) ou Decimal -> converti en float et inversé en [lon, lat].
        """
        if not cls._ors_enabled():
            return None
        try:
            import json
            base_url = 'https://api.openrouteservice.org/v2/matrix/driving-car'
            # ORS attend [lon, lat]
            src_lonlat = [float(source[1]), float(source[0])]
            dest_lonlat = [[float(lon), float(lat)] for (lat, lon) in destinations]
            locations = [src_lonlat] + dest_lonlat
            body = {
                'locations': locations,
                'sources': [0],
                'destinations': list(range(1, len(locations))),
                'metrics': ['duration'],
            }
            resp = requests.post(base_url, headers=cls._ors_headers(), data=json.dumps(body), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # durations: matrix sources x destinations, donc [ [d0->dest1, d0->dest2, ...] ]
            durations_sec = data.get('durations', [[]])[0]
            if durations_sec is None:
                return None
            return [(d or 0.0) / 60.0 for d in durations_sec]
        except Exception as e:
            print(f"ORS matrix error: {e}")
            return None

    @classmethod
    def _ors_full_matrix(cls, coords: List[Tuple[float, float]]) -> Optional[List[List[float]]]:
        """Durées (minutes) entre tous les points coords (lat, lon). Retourne matrice NxN."""
        if not cls._ors_enabled():
            return None
        try:
            import json
            base_url = 'https://api.openrouteservice.org/v2/matrix/driving-car'
            locations = [[float(lon), float(lat)] for (lat, lon) in coords]
            n = len(locations)
            body = {
                'locations': locations,
                'sources': list(range(n)),
                'destinations': list(range(n)),
                'metrics': ['duration'],
            }
            resp = requests.post(base_url, headers=cls._ors_headers(), data=json.dumps(body), timeout=20)
            resp.raise_for_status()
            data = resp.json()
            durs = data.get('durations') or []
            if not durs:
                return None
            # Convertir en minutes
            return [[(cell or 0.0)/60.0 for cell in row] for row in durs]
        except Exception as e:
            print(f"ORS full matrix error: {e}")
            return None

    # ==============================
    # Mapbox (prioritaire)
    # ==============================
    @staticmethod
    def _mb_enabled() -> bool:
        token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or ''
        return bool(token.strip())

    @classmethod
    def _mb_matrix_from_source(cls, source: Tuple[float, float], destinations: List[Tuple[float, float]]) -> Optional[List[float]]:
        """Durée en minutes de source -> chaque destination via Mapbox (one-to-many)."""
        if not cls._mb_enabled() or not destinations:
            return None
        try:
            token = getattr(settings, 'MAPBOX_ACCESS_TOKEN')
            # coords = [source] + destinations, format (lon,lat)
            coords = [[float(source[1]), float(source[0])]] + [[float(lon), float(lat)] for (lat, lon) in destinations]
            coord_str = ';'.join(f"{lon},{lat}" for lon, lat in coords)
            dest_idx = ';'.join(str(i) for i in range(1, len(coords)))  # 1..k

            url = (
                f"https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coord_str}"
                f"?annotations=duration&sources=0&destinations={dest_idx}"
                f"&access_token={token}"
            )

            # lightweight logger
            try:
                print(f"[MATRIX] one-to-many elements={len(destinations)} (src=1, dst={len(destinations)})")
            except Exception:
                pass

            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            durs = data.get('durations')
            if not durs:
                return None
            # ligne 0 = durées depuis la source vers toutes les destinations (déjà k valeurs)
            row0 = durs[0]
            return [(d or 0.0) / 60.0 for d in row0]
        except Exception as e:
            print(f"Mapbox matrix error: {e}")
            return None

    @classmethod
    def _mb_full_matrix(cls, coords: List[Tuple[float, float]]) -> Optional[List[List[float]]]:
        # Deprecated in low-consumption mode; kept for compatibility but unused
        return None

    @classmethod
    def _sequence_cost(cls, start_lat: Decimal, start_lon: Decimal, coords: List[Tuple[Decimal, Decimal]], *, use_matrix: bool = True) -> Tuple[float, str]:
        """
        Coût total (minutes) d'une séquence (start -> c0 -> c1 ...).
        - use_matrix=True : Mapbox OU ORS (arêtes consécutives en one-to-many).
        - use_matrix=False : Haversine à vitesse moyenne (pour 2-opt).
        """
        if not coords:
            mode = 'MAPBOX' if (use_matrix and cls._mb_enabled()) else (
                'ORS' if (use_matrix and getattr(settings, 'ROUTING_USE_ORS', False) and cls._ors_enabled()) else 'HAVERSINE'
            )
            return 0.0, mode

        # 1) Mapbox prioritaire
        if use_matrix and cls._mb_enabled():
            total_min = 0.0
            # start -> first
            d0 = cls._mb_matrix_from_source(
                (float(start_lat), float(start_lon)),
                [(float(coords[0][0]), float(coords[0][1]))]
            )
            total_min += float(d0[0]) if d0 else 0.0
            # paires consécutives
            for i in range(len(coords)-1):
                dij = cls._mb_matrix_from_source(
                    (float(coords[i][0]), float(coords[i][1])),
                    [(float(coords[i+1][0]), float(coords[i+1][1]))]
                )
                total_min += float(dij[0]) if dij else 0.0
            return total_min, 'MAPBOX'

        # 2) ORS si activé
        if use_matrix and getattr(settings, 'ROUTING_USE_ORS', False) and cls._ors_enabled():
            total_min = 0.0
            d0 = cls._ors_matrix_durations(
                (float(start_lat), float(start_lon)),
                [(float(coords[0][0]), float(coords[0][1]))]
            )
            total_min += float(d0[0]) if d0 else 0.0
            for i in range(len(coords)-1):
                dij = cls._ors_matrix_durations(
                    (float(coords[i][0]), float(coords[i][1])),
                    [(float(coords[i+1][0]), float(coords[i+1][1]))]
                )
                total_min += float(dij[0]) if dij else 0.0
            return total_min, 'ORS'

        # 3) Fallback : Haversine + vitesse moyenne
        avg_speed = getattr(settings, 'ROUTING_AVG_SPEED_KMH', 50)
        total_km = 0.0
        total_km += cls.calculate_distance(start_lat, start_lon, coords[0][0], coords[0][1])
        for i in range(len(coords)-1):
            total_km += cls.calculate_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
        return (total_km / float(avg_speed)) * 60.0, 'HAVERSINE'

    @classmethod
    def _improve_2opt(cls, start_lat: Decimal, start_lon: Decimal, items: List[dict]) -> List[dict]:
        """Applique 2-opt sur la séquence items (ayant 'lat','lon')."""
        route = items[:]
        def route_coords(seq):
            return [(p['lat'], p['lon']) for p in seq]
        best_cost, _ = cls._sequence_cost(start_lat, start_lon, route_coords(route), use_matrix=False)
        improved = True
        while improved:
            improved = False
            for i in range(len(route) - 2):
                for k in range(i + 1, len(route) - 1):
                    new_route = route[:i] + route[i:k+1][::-1] + route[k+1:]
                    new_cost, _ = cls._sequence_cost(start_lat, start_lon, route_coords(new_route), use_matrix=False)
                    if new_cost < best_cost:
                        route = new_route
                        best_cost = new_cost
                        improved = True
                        break
                if improved:
                    break
        return route

    @classmethod
    def nearest_neighbor_optimization(cls, commercial: Commercial, date_rdv: str, max_rdv: int = 7) -> List[Rendezvous]:
        """
        Optimise l'ordre des rendez-vous avec l'algorithme Nearest Neighbor
        """
        # Récupération des rendez-vous à venir pour ce commercial à cette date
        rdvs = (Rendezvous.objects
                .filter(commercial=commercial, date_rdv=date_rdv, statut_rdv='a_venir')
                .select_related('client')
                .order_by('heure_rdv')[:max_rdv])

        if not rdvs:
            return []

        # Récupération des adresses des clients avec coordonnées
        rdvs_with_coords = []
        for rdv in rdvs:
            if rdv.client:
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
            return []

        # Point de départ (domicile du commercial)
        if commercial.latitude_depart and commercial.longitude_depart:
            start_lat = commercial.latitude_depart
            start_lon = commercial.longitude_depart
        else:
            # Si pas de point de départ, utiliser le premier rendez-vous
            start_lat = rdvs_with_coords[0]['lat']
            start_lon = rdvs_with_coords[0]['lon']

        # Algorithme Nearest Neighbor (coût = Mapbox/ORS si dispo, sinon distance Haversine)
        optimized_route = []
        current_lat, current_lon = start_lat, start_lon
        unvisited = rdvs_with_coords.copy()

        while unvisited:
            dest_coords = [(item['lat'], item['lon']) for item in unvisited]

            # Priorité: MAPBOX -> ORS -> Haversine
            durations = None
            if cls._mb_enabled():
                durations = cls._mb_matrix_from_source((float(current_lat), float(current_lon)),
                                                       [(float(lat), float(lon)) for (lat, lon) in dest_coords])
            if durations is None and getattr(settings, 'ROUTING_USE_ORS', False) and cls._ors_enabled():
                durations = cls._ors_matrix_durations((float(current_lat), float(current_lon)),
                                                      [(float(lat), float(lon)) for (lat, lon) in dest_coords])

            min_cost = float('inf')
            nearest_idx = 0
            if durations:
                for i, dur in enumerate(durations):
                    cost = float(dur)
                    if cost < min_cost:
                        min_cost = cost
                        nearest_idx = i
            else:
                # fallback distance
                for i, rdv_data in enumerate(unvisited):
                    distance = cls.calculate_distance(
                        current_lat, current_lon,
                        rdv_data['lat'], rdv_data['lon']
                    )
                    if distance < min_cost:
                        min_cost = distance
                        nearest_idx = i

            # Ajouter le rendez-vous le plus proche à la route
            nearest_rdv = unvisited.pop(nearest_idx)
            optimized_route.append(nearest_rdv['rdv'])

            # Mettre à jour la position actuelle
            current_lat = nearest_rdv['lat']
            current_lon = nearest_rdv['lon']

        # Passe d'amélioration 2-opt sur la séquence retenue
        seq_items = []
        for rdv in optimized_route:
            addr = rdv.client.adresses.filter(latitude__isnull=False, longitude__isnull=False).first() if rdv.client else None
            if addr:
                seq_items.append({'rdv': rdv, 'lat': addr.latitude, 'lon': addr.longitude})
        if seq_items:
            improved_items = cls._improve_2opt(start_lat, start_lon, seq_items)
            optimized_route = [it['rdv'] for it in improved_items]

        return optimized_route

    @classmethod
    def reorder_day_assign_slots(cls, commercial: Commercial, d: date) -> int:
        """Réordonne les RDV 'a_venir' d'un commercial pour une date donnée et assigne des créneaux.
        Retourne le nombre de RDV réordonnés.
        """
        rdvs = cls.nearest_neighbor_optimization(commercial, d.isoformat(), max_rdv=7)
        if not rdvs:
            return 0
        # Créneaux: de 09:00 à 12:00, pas au-delà de 12:30
        creneaux = [
            dtime(9, 0),
            dtime(9, 30),
            dtime(10, 0),
            dtime(10, 30),
            dtime(11, 0),
            dtime(11, 30),
            dtime(12, 0),
        ]
        changed = 0
        for idx, rdv in enumerate(rdvs):
            if idx >= len(creneaux):
                break
            new_time = creneaux[idx]
            if rdv.heure_rdv != new_time:
                rdv.heure_rdv = new_time
                rdv.save(update_fields=['heure_rdv'])
                changed += 1
        return changed

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
                'estimated_time_minutes': 0,
                'mode': 'HAVERSINE'
            }

        # Calcul de la distance totale (vol d'oiseau sur la séquence finale)
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

        # Point de départ
        if commercial.latitude_depart and commercial.longitude_depart:
            start_lat = commercial.latitude_depart
            start_lon = commercial.longitude_depart
        else:
            start_lat = route_details[0]['address'].latitude if route_details else 0
            start_lon = route_details[0]['address'].longitude if route_details else 0

        # Coordonnées dans l'ordre final
        coords = []
        for rdv in optimized_rdvs:
            if rdv.client:
                address = rdv.client.adresses.filter(latitude__isnull=False, longitude__isnull=False).first()
                if address:
                    coords.append((address.latitude, address.longitude))

        # Temps final : Mapbox OU ORS (arêtes consécutives) si dispo, sinon Haversine
        use_matrix = cls._mb_enabled() or (getattr(settings, 'ROUTING_USE_ORS', False) and cls._ors_enabled())
        est_min, mode = cls._sequence_cost(start_lat, start_lon, coords, use_matrix=use_matrix)
        estimated_time_minutes = int(est_min)

        return {
            'rdvs': optimized_rdvs,
            'route_details': route_details,
            'total_distance': round(total_distance, 2),
            'estimated_time_minutes': estimated_time_minutes,
            'mode': mode
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


def _get_commercial_start(commercial: Commercial) -> Optional[Tuple[Decimal, Decimal]]:
    if commercial.latitude_depart and commercial.longitude_depart:
        return Decimal(commercial.latitude_depart), Decimal(commercial.longitude_depart)
    return None


def _get_first_client_coords(client: FrontClient) -> Optional[Tuple[Decimal, Decimal]]:
    addr = client.adresses.filter(latitude__isnull=False, longitude__isnull=False).first()
    if not addr:
        return None
    return Decimal(addr.latitude), Decimal(addr.longitude)


def _estimate_day_distance_km(commercial: Commercial, d: date) -> float:
    """Estimation simple de la distance cumulée du jour avec Haversine (ordre actuel)."""
    rdvs = list(Rendezvous.objects.filter(commercial=commercial, date_rdv=d, statut_rdv='a_venir').order_by('heure_rdv'))
    if not rdvs:
        return 0.0
    total = 0.0
    start = _get_commercial_start(commercial)
    prev = None
    if start:
        prev = start
    for rdv in rdvs:
        if not rdv.client:
            continue
        coords = _get_first_client_coords(rdv.client)
        if not coords:
            continue
        if prev is None:
            prev = coords
            continue
        total += float(RouteOptimizationService.calculate_distance(prev[0], prev[1], coords[0], coords[1]))
        prev = coords
    return total


def _build_clusters(points: List[Tuple[FrontClient, Decimal, Decimal]], radius_km: float) -> List[List[Tuple[FrontClient, Decimal, Decimal]]]:
    """Clustering simple par rayon: on groupe les points proches (single-link)."""
    clusters: List[List[Tuple[FrontClient, Decimal, Decimal]]] = []
    for item in points:
        placed = False
        for cl in clusters:
            # si proche de au moins un point du cluster
            for (_, lat, lon) in cl:
                if RouteOptimizationService.calculate_distance(lat, lon, item[1], item[2]) <= float(radius_km):
                    cl.append(item)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([item])
    return clusters


def _cluster_score(cluster: List[Tuple[FrontClient, Decimal, Decimal]], start_lat: Decimal, start_lon: Decimal) -> Tuple[int, float]:
    """Score: (-taille, distance du centroïde au départ). Plus petit est mieux."""
    size = len(cluster)
    # centroïde simple
    if size == 0:
        return (0, float('inf'))
    avg_lat = sum([float(lat) for (_, lat, _) in cluster]) / size
    avg_lon = sum([float(lon) for (_, _, lon) in cluster]) / size
    dist = RouteOptimizationService.calculate_distance(Decimal(avg_lat), Decimal(avg_lon), start_lat, start_lon)
    return (-size, dist)


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
        start_coords = _get_commercial_start(commercial)
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

        clients_all = list(clients_qs)
        # Construire les points (client, lat, lon)
        points: List[Tuple[FrontClient, Decimal, Decimal]] = []
        if start_coords:
            s_lat, s_lon = start_coords
        for c in clients_all:
            coords = _get_first_client_coords(c)
            if not coords:
                continue
            points.append((c, coords[0], coords[1]))

        # Filtre rayon global d'abord
        max_radius_km = getattr(settings, 'MAX_RADIUS_KM', 0) or 0
        if start_coords and max_radius_km > 0:
            points = [(c, lat, lon) for (c, lat, lon) in points if RouteOptimizationService.calculate_distance(s_lat, s_lon, lat, lon) <= float(max_radius_km)]

        # Clustering par rayon pour garder une zone homogène
        cluster_radius = getattr(settings, 'CLUSTER_RADIUS_KM', 10) or 10
        if start_coords and points:
            clusters = _build_clusters(points, float(cluster_radius))
            clusters = sorted(clusters, key=lambda cl: _cluster_score(cl, s_lat, s_lon))
            # On ne garde que le cluster le plus dense/proche
            main_cluster = clusters[0]
            # Sélection gloutonne ancrée au départ: 1) plus proche du départ, puis
            # 2) à chaque étape, on prend le plus proche du dernier choisi, jusqu'à 7
            remaining = [(c, lat, lon) for (c, lat, lon) in main_cluster]
            selected: List[FrontClient] = []
            if remaining:
                # premier: plus proche du départ
                first_idx = min(
                    range(len(remaining)),
                    key=lambda i: RouteOptimizationService.calculate_distance(s_lat, s_lon, remaining[i][1], remaining[i][2])
                )
                c, lat, lon = remaining.pop(first_idx)
                selected.append(c)
                cur_lat, cur_lon = lat, lon
                # suivants: plus proche du dernier point choisi
                while remaining and len(selected) < 7:
                    next_idx = min(
                        range(len(remaining)),
                        key=lambda i: RouteOptimizationService.calculate_distance(cur_lat, cur_lon, remaining[i][1], remaining[i][2])
                    )
                    c, lat, lon = remaining.pop(next_idx)
                    selected.append(c)
                    cur_lat, cur_lon = lat, lon
            clients = selected
        else:
            # fallback: proximité simple au départ
            def score_tuple(item):
                c, lat, lon = item
                return RouteOptimizationService.calculate_distance(s_lat, s_lon, lat, lon) if start_coords else 0.0
            clients = [c for (c, _, __) in sorted(points, key=score_tuple)]

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
                        # Vérifier la limite de distance journalière estimée
                        max_daily_km = getattr(settings, 'MAX_DAILY_DISTANCE_KM', 0) or 0
                        if max_daily_km > 0:
                            # on calcule après insertion; si dépassement on annule
                            est = _estimate_day_distance_km(commercial, d)
                            if est > float(max_daily_km):
                                obj.delete()
                                continue
                        created_count += 1
                        capacity_by_day[d] -= 1
                        manquants -= 1
                        if collect_breakdown:
                            per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
                            per_commercial_per_day[commercial.id][d.isoformat()] = per_commercial_per_day[commercial.id].get(d.isoformat(), 0) + 1
                    else:
                        skipped_existing += 1

        # Après traitement de tous les clients: réordonner les RDV de chaque jour
        for d in business_days:
            try:
                RouteOptimizationService.reorder_day_assign_slots(commercial, d)
            except Exception as e:
                print(f"Reorder failed for {commercial} {d}: {e}")

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
