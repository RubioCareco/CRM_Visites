import requests
import time
import logging
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
from django.utils import timezone
from datetime import date, datetime, timedelta, time as dtime
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from .models import Adresse, Commercial, Rendezvous, FrontClient, ClientVisitStats
import unicodedata  # normalisation noms clients

logger = logging.getLogger(__name__)


def _norm_name_from_client(cli: FrontClient) -> str:
    """
    Nom normalisé pour éviter les doublons 'même nom' (accents/majuscules/espaces).
    """
    base = (
        getattr(cli, "rs_nom", None)
        or f"{getattr(cli, 'nom', '')} {getattr(cli, 'prenom', '')}".strip()
        or str(cli)
    )
    s = unicodedata.normalize("NFKD", base or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(ch for ch in s if ch.isalnum() or ch in " .-_")


class GeocodingService:
    """Service pour géocoder les adresses avec Nominatim (OpenStreetMap)"""

    BASE_URL = "https://nominatim.openstreetmap.org/search"

    @classmethod
    def geocode_address(
        cls, adresse: str, code_postal: str, ville: str
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Géocode une adresse avec logique de fallback
        """
        headers = {
            "User-Agent": "CRM-Visites/1.0 (https://github.com/your-repo)"
        }

        # Essai 1 : Adresse complète
        full_address = f"{adresse}, {code_postal} {ville}, France"
        coords = cls._try_geocode(full_address, headers)
        if coords:
            return coords

        # Essai 2 : Sans le nom d'entreprise (prendre après le premier tiret ou espace)
        if " - " in adresse:
            clean_address = adresse.split(" - ")[-1].strip()
        elif " " in adresse and not adresse[0].isdigit():
            parts = adresse.split(" ", 1)
            clean_address = parts[1] if len(parts) > 1 else adresse
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
    def _try_geocode(
        cls, address: str, headers: dict
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Essaie de géocoder une adresse
        """
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "fr",
        }

        try:
            response = requests.get(
                cls.BASE_URL, params=params, headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                lat = Decimal(data[0]["lat"])
                lon = Decimal(data[0]["lon"])
                return lat, lon
        except Exception:
            logger.exception("Echec geocodage pour %s", address)

        return None

    @classmethod
    def geocode_all_addresses(cls):
        """
        Géocode toutes les adresses qui n'ont pas encore de coordonnées
        """
        addresses = Adresse.objects.filter(
            latitude__isnull=True, longitude__isnull=True
        )

        for address in addresses:
            if address.adresse and address.code_postal and address.ville:
                coords = cls.geocode_address(
                    address.adresse, address.code_postal, address.ville
                )

                if coords:
                    address.latitude, address.longitude = coords
                    address.geocode_date = timezone.now()
                    address.save()
                    logger.info("Adresse geocodee: %s", address)
                else:
                    logger.warning("Echec geocodage adresse: %s", address)

                # Pause pour respecter les limites de l'API
                time.sleep(1)


class RouteOptimizationService:
    """Service d'optimisation de trajet avec algorithme Nearest Neighbor.

    Modes de coût (priorité) :
    - Google Maps (durée routière) : Distance Matrix / Directions
    - Haversine (vol d'oiseau) en repli
    """

    # ==============================
    # Distance "vol d'oiseau"
    # ==============================
    @classmethod
    def calculate_distance(
        cls, lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal
    ) -> float:
        """
        Calcule la distance en km entre deux points (formule de Haversine)
        """
        from math import radians, cos, sin, asin, sqrt

        lat1, lon1, lat2, lon2 = map(
            radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
        )
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371  # Rayon de la Terre en km
        return c * r

    # ==============================
    # Google Maps (prioritaire)
    # ==============================
    @staticmethod
    def _gm_enabled() -> bool:
        key = getattr(settings, "GOOGLE_MAPS_API_KEY", "") or ""
        return bool(key.strip())

    # Petit limiteur de débit "soft" pour éviter de spammer l'API
    _GM_LAST_CALL_TS: float = 0.0
    _GM_MIN_INTERVAL_SEC: float = 0.2  # ~5 req/s max

    @classmethod
    def _gm_rate_limit(cls) -> None:
        now = time.time()
        delta = now - cls._GM_LAST_CALL_TS
        if delta < cls._GM_MIN_INTERVAL_SEC:
            time.sleep(cls._GM_MIN_INTERVAL_SEC - delta)
        cls._GM_LAST_CALL_TS = time.time()

    @classmethod
    def _gm_distance_matrix_from_source(
        cls,
        source: tuple[float, float],
        destinations: list[tuple[float, float]],
        timeout: int = 15,
    ) -> Optional[list[float]]:
        """Durée en minutes source -> chaque destination via Google Distance Matrix.

        Implémentation centralisée : réutilise google_distance_matrix_one_to_many().
        Fallback Haversine si un élément n'a pas de route.
        """
        if not cls._gm_enabled() or not destinations:
            return None

        # Appel centralisé (avec rate-limit de la classe)
        rows = google_distance_matrix_one_to_many(
            source,
            destinations,
            timeout=timeout,
            rate_limit=cls._gm_rate_limit,
        )
        if not rows:
            return None

        results: list[float] = []
        avg_speed = float(getattr(settings, "ROUTING_AVG_SPEED_KMH", 50))

        for elem, (lat, lon) in zip(rows, destinations):
            st = (elem or {}).get("status")
            dur_s = (elem or {}).get("duration_s")

            if st == "OK" and dur_s is not None:
                results.append(float(dur_s) / 60.0)
            else:
                # Fallback Haversine si pas de résultat routier
                km = cls.calculate_distance(
                    Decimal(source[0]),
                    Decimal(source[1]),
                    Decimal(lat),
                    Decimal(lon),
                )
                results.append((km / avg_speed) * 60.0)

        return results

    @classmethod
    def _gm_directions_metrics(
        cls,
        source: Tuple[float, float],
        dest: Tuple[float, float],
        timeout: int = 15,
    ) -> Optional[Tuple[float, float]]:
        """
        Appelle Google Directions (driving) pour A->B et renvoie (durée_sec, distance_km).
        source, dest sont au format (lat, lon).
        """
        if not cls._gm_enabled():
            return None

        key = getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()
        if not key:
            return None

        origin = f"{source[0]},{source[1]}"
        destination = f"{dest[0]},{dest[1]}"

        params = {
            "origin": origin,
            "destination": destination,
            "mode": getattr(settings, "GOOGLE_MAPS_TRAVEL_MODE", "driving"),
            "units": "metric",
            "key": key,
        }

        try:
            cls._gm_rate_limit()
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "OK":
                logger.warning("Google Directions status != OK: %s", data.get("status"))
                return None

            route0 = data.get("routes", [{}])[0]
            leg0 = route0.get("legs", [{}])[0]
            secs = float(leg0["duration"]["value"])
            km = float(leg0["distance"]["value"]) / 1000.0
            return secs, km

        except Exception:
            logger.exception("Google Directions error")
            return None

    # ==============================
    # Coût d'une séquence
    # ==============================
    @classmethod
    def _sequence_cost(
        cls,
        start_lat: Decimal,
        start_lon: Decimal,
        coords: List[Tuple[Decimal, Decimal]],
        *,
        use_matrix: bool = True,
    ) -> Tuple[float, str]:
        """
        Coût total (minutes) d'une séquence (start -> c0 -> c1 ...).
        - use_matrix=True et Google activé : temps routier via Distance Matrix / Directions.
        - sinon : Haversine + vitesse moyenne.
        """
        if not coords:
            mode = "GOOGLE" if (use_matrix and cls._gm_enabled()) else "HAVERSINE"
            return 0.0, mode

        avg_speed = float(getattr(settings, "ROUTING_AVG_SPEED_KMH", 50))

        # 1) Google prioritaire
        if use_matrix and cls._gm_enabled():
            total_min = 0.0

            # start -> first
            d0 = cls._gm_distance_matrix_from_source(
                (float(start_lat), float(start_lon)),
                [(float(coords[0][0]), float(coords[0][1]))],
            )
            if d0 is None:
                km = cls.calculate_distance(start_lat, start_lon, coords[0][0], coords[0][1])
                total_min += (km / avg_speed) * 60.0
            else:
                total_min += float(d0[0])

            # paires consécutives
            for i in range(len(coords) - 1):
                dij = cls._gm_distance_matrix_from_source(
                    (float(coords[i][0]), float(coords[i][1])),
                    [(float(coords[i + 1][0]), float(coords[i + 1][1]))],
                )
                if dij is None:
                    km = cls.calculate_distance(
                        coords[i][0],
                        coords[i][1],
                        coords[i + 1][0],
                        coords[i + 1][1],
                    )
                    total_min += (km / avg_speed) * 60.0
                else:
                    total_min += float(dij[0])

            return total_min, "GOOGLE"

        # 2) Fallback : Haversine + vitesse moyenne
        total_km = 0.0
        total_km += cls.calculate_distance(start_lat, start_lon, coords[0][0], coords[0][1])
        for i in range(len(coords) - 1):
            total_km += cls.calculate_distance(
                coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
            )

        return (total_km / avg_speed) * 60.0, "HAVERSINE"

    # ==============================
    # 2-opt (amélioration locale)
    # ==============================
    @classmethod
    def _improve_2opt(
        cls, start_lat: Decimal, start_lon: Decimal, items: List[dict]
    ) -> List[dict]:
        """Applique 2-opt sur la séquence items (ayant 'lat','lon')."""
        route = items[:]

        def route_coords(seq):
            return [(p["lat"], p["lon"]) for p in seq]

        # Pour 2-opt on reste en Haversine (rapide, pas d'appels API)
        best_cost, _ = cls._sequence_cost(
            start_lat, start_lon, route_coords(route), use_matrix=False
        )
        improved = True
        while improved:
            improved = False
            for i in range(len(route) - 2):
                for k in range(i + 1, len(route) - 1):
                    new_route = route[:i] + route[i : k + 1][::-1] + route[k + 1 :]
                    new_cost, _ = cls._sequence_cost(
                        start_lat,
                        start_lon,
                        route_coords(new_route),
                        use_matrix=False,
                    )
                    if new_cost < best_cost:
                        route = new_route
                        best_cost = new_cost
                        improved = True
                        break
                if improved:
                    break
        return route

    # ==============================
    # Nearest Neighbor (ordre des RDV)
    # ==============================
    @classmethod
    def nearest_neighbor_optimization(
        cls,
        commercial: Commercial,
        date_rdv: str,
        max_rdv: int = 6,
    ) -> List[Rendezvous]:
        """
        Optimise l'ordre des rendez-vous avec l'algorithme Nearest Neighbor.
        Utilise Google Distance Matrix quand disponible, sinon Haversine.
        """
        rdvs = (
            Rendezvous.objects.filter(
                commercial=commercial, date_rdv=date_rdv, statut_rdv="a_venir"
            )
            .select_related("client")
            .order_by("heure_rdv")[:max_rdv]
        )

        if not rdvs:
            return []

        # Adresses avec coordonnées
        rdvs_with_coords = []
        for rdv in rdvs:
            if rdv.client:
                address = rdv.client.adresses.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                ).first()
                if address:
                    rdvs_with_coords.append(
                        {
                            "rdv": rdv,
                            "lat": address.latitude,
                            "lon": address.longitude,
                            "address": address,
                        }
                    )

        if not rdvs_with_coords:
            return []

        # Point de départ
        if commercial.latitude_depart and commercial.longitude_depart:
            start_lat = commercial.latitude_depart
            start_lon = commercial.longitude_depart
        else:
            start_lat = rdvs_with_coords[0]["lat"]
            start_lon = rdvs_with_coords[0]["lon"]

        # Option: filtrer les RDV très éloignés du point de départ
        max_radius_km = getattr(settings, "MAX_RADIUS_KM", 0) or 0
        if commercial.latitude_depart and commercial.longitude_depart and max_radius_km > 0:
            s_lat, s_lon = commercial.latitude_depart, commercial.longitude_depart
            filtered = []
            for item in rdvs_with_coords:
                d = cls.calculate_distance(s_lat, s_lon, item["lat"], item["lon"])
                if d <= float(max_radius_km):
                    filtered.append(item)
            if filtered:
                rdvs_with_coords = filtered

        # Nearest Neighbor
        optimized_route: List[Rendezvous] = []
        current_lat, current_lon = start_lat, start_lon
        unvisited = rdvs_with_coords.copy()

        while unvisited:
            dest_coords = [(item["lat"], item["lon"]) for item in unvisited]

            durations = None
            if cls._gm_enabled():
                durations = cls._gm_distance_matrix_from_source(
                    (float(current_lat), float(current_lon)),
                    [(float(lat), float(lon)) for (lat, lon) in dest_coords],
                )

            min_cost = float("inf")
            nearest_idx = 0
            if durations:
                for i, dur in enumerate(durations):
                    cost = float(dur)
                    if cost < min_cost:
                        min_cost = cost
                        nearest_idx = i
            else:
                for i, rdv_data in enumerate(unvisited):
                    distance = cls.calculate_distance(
                        current_lat, current_lon,
                        rdv_data["lat"], rdv_data["lon"],
                    )
                    if distance < min_cost:
                        min_cost = distance
                        nearest_idx = i

            # Ajouter le rendez-vous le plus proche
            nearest_rdv = unvisited.pop(nearest_idx)
            optimized_route.append(nearest_rdv["rdv"])

            # Mise à jour position actuelle
            current_lat = nearest_rdv["lat"]
            current_lon = nearest_rdv["lon"]

        # Amélioration 2-opt (Haversine only)
        seq_items = []
        for rdv in optimized_route:
            addr = (
                rdv.client.adresses.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                ).first()
                if rdv.client
                else None
            )
            if addr:
                seq_items.append({"rdv": rdv, "lat": addr.latitude, "lon": addr.longitude})

        if seq_items:
            improved_items = cls._improve_2opt(start_lat, start_lon, seq_items)
            optimized_route = [it["rdv"] for it in improved_items]

        return optimized_route

    # ==============================
    # Réordonnancement + créneaux
    # ==============================
    @classmethod
    def reorder_day_assign_slots(cls, commercial: Commercial, d: date) -> int:
        """Réordonne les RDV 'a_venir' d'un commercial pour une date donnée et assigne des créneaux."""
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
                rdv.save(update_fields=["heure_rdv"])
                changed += 1
        return changed

    # ==============================
    # Route optimisée + distance/temps
    # ==============================
    @classmethod
    def get_optimized_route_for_commercial(
        cls, commercial: Commercial, date_rdv: str
    ) -> dict:
        """
        Retourne une route optimisée avec les informations de distance.
        Addition des métriques Google segmentaires quand disponibles.
        """
        optimized_rdvs = cls.nearest_neighbor_optimization(commercial, date_rdv)

        if not optimized_rdvs:
            return {
                "rdvs": [],
                "route_details": [],
                "total_distance": 0,
                "estimated_time_minutes": 0,
                "mode": "HAVERSINE",
            }

        # Point de départ
        if commercial.latitude_depart and commercial.longitude_depart:
            start_lat = commercial.latitude_depart
            start_lon = commercial.longitude_depart
        else:
            first_addr = optimized_rdvs[0].client.adresses.filter(
                latitude__isnull=False,
                longitude__isnull=False,
            ).first()
            start_lat = first_addr.latitude if first_addr else Decimal("0")
            start_lon = first_addr.longitude if first_addr else Decimal("0")

        # Coordonnées ordonnées (séquence finale)
        coords: List[Tuple[Decimal, Decimal]] = []
        route_details = []
        current_lat = start_lat
        current_lon = start_lon

        for rdv in optimized_rdvs:
            if rdv.client:
                address = rdv.client.adresses.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                ).first()
                if address:
                    hav_km = cls.calculate_distance(
                        current_lat, current_lon, address.latitude, address.longitude
                    )
                    route_details.append(
                        {
                            "rdv": rdv,
                            "distance_from_previous": hav_km,
                            "address": address,
                        }
                    )
                    coords.append((address.latitude, address.longitude))
                    current_lat, current_lon = address.latitude, address.longitude

        # Temps final : Google si dispo, sinon Haversine
        use_matrix = cls._gm_enabled()
        est_min, mode = cls._sequence_cost(start_lat, start_lon, coords, use_matrix=use_matrix)
        estimated_time_minutes = int(est_min)

        # Total distance via Directions Google (si possible)
        total_distance_km_google = 0.0
        used_google_any = False
        if cls._gm_enabled() and coords:
            segs: List[Tuple[Tuple[Decimal, Decimal], Tuple[Decimal, Decimal]]] = []
            prev = (start_lat, start_lon)
            for lat, lon in coords:
                segs.append((prev, (lat, lon)))
                prev = (lat, lon)

            for (a, b) in segs:
                res = cls._gm_directions_metrics(
                    (float(a[0]), float(a[1])),
                    (float(b[0]), float(b[1])),
                )
                if res is not None:
                    secs, km = res
                    total_distance_km_google += km
                    used_google_any = True
                else:
                    total_distance_km_google += cls.calculate_distance(a[0], a[1], b[0], b[1])

        if used_google_any:
            total_distance = round(total_distance_km_google, 2)
            mode_out = "GOOGLE"
        else:
            total_distance = round(
                sum(x["distance_from_previous"] for x in route_details), 2
            )
            mode_out = mode

        return {
            "rdvs": optimized_rdvs,
            "route_details": route_details,
            "total_distance": total_distance,
            "estimated_time_minutes": estimated_time_minutes,
            "mode": mode_out,
        }


# ============================
# Planification des rendez-vous
# ============================

CLASSEMENT_TO_TARGET_28D: Dict[str, int] = {
    "A": 10,
    "B": 5,
    "C": 1,
    "": 1,  # N/A
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
                country_class = getattr(pyholidays, "FR", None)
            if country_class is None:
                continue
            for d in country_class(years=y):
                dates.add(d.strftime("%Y-%m-%d"))
    except Exception:
        return set()
    return dates


def _get_holiday_set() -> set[str]:
    """Construit l'ensemble des jours fériés en ISO-8601 (YYYY-MM-DD)."""
    manual: set[str] = set(getattr(settings, "PUBLIC_HOLIDAYS", []) or [])

    country = getattr(settings, "HOLIDAYS_COUNTRY", None)
    years_csv = getattr(settings, "HOLIDAYS_YEARS", None)

    if not country or not years_csv:
        return manual

    try:
        years = [int(x.strip()) for x in str(years_csv).split(",") if x.strip()]
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
    holiday_set = _get_holiday_set()
    return target_date.isoformat() not in holiday_set


def _count_rdv_non_annules_for_commercial_on_date(
    commercial: Commercial, d: date
) -> int:
    return (
        Rendezvous.objects.filter(commercial=commercial, date_rdv=d)
        .exclude(statut_rdv="annule")
        .count()
    )


def _rdv_exists_for_client_on_date(
    client: FrontClient, commercial: Commercial, d: date
) -> bool:
    return (
        Rendezvous.objects.filter(client=client, commercial=commercial, date_rdv=d)
        .exclude(statut_rdv="annule")
        .exists()
    )


def _get_objectif_annuel(
    client: FrontClient, commercial: Commercial, annee: int
) -> int:
    stats = ClientVisitStats.objects.filter(
        client=client, commercial=commercial, annee=annee
    ).first()
    if stats:
        return stats.objectif
    classement = (client.classement_client or "").upper().strip()
    return CLASSEMENT_TO_TARGET_28D.get(classement, 1)


def _get_visites_valides_annee(
    client: FrontClient, commercial: Commercial, annee: int
) -> int:
    return Rendezvous.objects.filter(
        client=client,
        commercial=commercial,
        date_rdv__year=annee,
        statut_rdv="valide",
    ).count()


def _get_already_planned_in_horizon(
    client: FrontClient, commercial: Commercial, start_d: date, end_d: date
) -> int:
    return (
        Rendezvous.objects.filter(
            client=client,
            commercial=commercial,
            date_rdv__gte=start_d,
            date_rdv__lte=end_d,
        )
        .exclude(statut_rdv="annule")
        .count()
    )


def _iter_business_days(start_d: date, end_d: date):
    d = start_d
    while d <= end_d:
        if _is_business_day(d):
            yield d
        d += timedelta(days=1)


def _get_commercial_start(
    commercial: Commercial,
) -> Optional[Tuple[Decimal, Decimal]]:
    if commercial.latitude_depart and commercial.longitude_depart:
        return (
            Decimal(commercial.latitude_depart),
            Decimal(commercial.longitude_depart),
        )
    return None


def _get_first_client_coords(
    client: FrontClient,
) -> Optional[Tuple[Decimal, Decimal]]:
    addr = client.adresses.filter(
        latitude__isnull=False, longitude__isnull=False
    ).first()
    if not addr:
        return None
    return Decimal(addr.latitude), Decimal(addr.longitude)


def _estimate_day_distance_km(commercial: Commercial, d: date) -> float:
    """Estimation simple de la distance cumulée du jour avec Haversine (ordre actuel)."""
    rdvs = list(
        Rendezvous.objects.filter(
            commercial=commercial, date_rdv=d, statut_rdv="a_venir"
        ).order_by("heure_rdv")
    )
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
        total += float(
            RouteOptimizationService.calculate_distance(
                prev[0], prev[1], coords[0], coords[1]
            )
        )
        prev = coords
    return total


def _build_clusters(
    points: List[Tuple[FrontClient, Decimal, Decimal]], radius_km: float
) -> List[List[Tuple[FrontClient, Decimal, Decimal]]]:
    """Clustering simple par rayon: on groupe les points proches (single-link)."""
    clusters: List[List[Tuple[FrontClient, Decimal, Decimal]]] = []
    for item in points:
        placed = False
        for cl in clusters:
            # si proche de au moins un point du cluster
            for (_, lat, lon) in cl:
                if (
                    RouteOptimizationService.calculate_distance(
                        lat, lon, item[1], item[2]
                    )
                    <= float(radius_km)
                ):
                    cl.append(item)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([item])
    return clusters


def _cluster_score(
    cluster: List[Tuple[FrontClient, Decimal, Decimal]],
    start_lat: Decimal,
    start_lon: Decimal,
) -> Tuple[int, float]:
    """Score: (-taille, distance du centroïde au départ). Plus petit est mieux."""
    size = len(cluster)
    # centroïde simple
    if size == 0:
        return (0, float("inf"))
    avg_lat = sum([float(lat) for (_, lat, _) in cluster]) / size
    avg_lon = sum([float(lon) for (_, _, lon) in cluster]) / size
    dist = RouteOptimizationService.calculate_distance(
        Decimal(avg_lat), Decimal(avg_lon), start_lat, start_lon
    )
    return (-size, dist)


# --- Sélection “par zone” : grappe compacte de k clients autour d'un centre (Haversine)
def _pick_k_zone_cluster(
    points: List[Tuple[FrontClient, Decimal, Decimal]],
    start_lat: Decimal,
    start_lon: Decimal,
    *,
    k: int = 6,
    spread_km: float = 20.0,  # compacité intra-groupe (paire max)
    seed_limit: int = 60,  # nb de centres testés (les plus proches du départ)
) -> List[FrontClient]:
    """
    Choisit une *grappe* compacte de k clients :
    - on teste plusieurs centres (seeds) proches du départ (Haversine),
    - pour chaque seed on prend ses plus proches (distance Haversine),
      en vérifiant la compacité pairwise (<= spread_km),
    - on score la grappe par (max distance pairwise, moyenne pairwise, distance centroïde→départ).
    """
    R = RouteOptimizationService
    if not points:
        return []

    def dkm(a_lat, a_lon, b_lat, b_lon) -> float:
        return R.calculate_distance(a_lat, a_lon, b_lat, b_lon)

    # 1) centres candidats = points les plus proches du départ
    pts_sorted = sorted(points, key=lambda t: dkm(start_lat, start_lon, t[1], t[2]))
    seeds = pts_sorted[: min(seed_limit, len(pts_sorted))]

    best_score = (float("inf"), float("inf"), float("inf"))
    best_group: List[Tuple[FrontClient, Decimal, Decimal]] = []

    for seed in seeds:
        seed_cli, s_lat, s_lon = seed

        # coûts seed -> tous (Haversine)
        order_idx = list(range(len(points)))
        order_idx.sort(key=lambda i: dkm(s_lat, s_lon, points[i][1], points[i][2]))

        # construit la grappe en respectant la compacité pairwise
        group: List[Tuple[FrontClient, Decimal, Decimal]] = [seed]
        for i in order_idx:
            if points[i][0].id == seed_cli.id:
                continue
            cand = points[i]
            ok = True
            for (_, la, lo) in group:
                if dkm(la, lo, cand[1], cand[2]) > spread_km:
                    ok = False
                    break
            if ok:
                group.append(cand)
                if len(group) == k:
                    break

        if len(group) == 0:
            continue

        # score: (max pairwise, moyenne pairwise, distance centroid->start)
        pair = []
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                pair.append(dkm(group[a][1], group[a][2], group[b][1], group[b][2]))
        max_pair = max(pair) if pair else 0.0
        avg_pair = sum(pair) / len(pair) if pair else 0.0
        c_lat = sum(float(la) for (_, la, _) in group) / len(group)
        c_lon = sum(float(lo) for (_, _, lo) in group) / len(group)
        c_dist = dkm(Decimal(c_lat), Decimal(c_lon), start_lat, start_lon)

        score = (max_pair, avg_pair, c_dist)
        if score < best_score:
            best_score = score
            best_group = group

    return [c for (c, _, __) in best_group[:k]]


# --- Sélection "plus proche voisin" depuis le point de départ (Haversine)
def _pick_k_stepwise_nearest(
    points: List[Tuple[FrontClient, Decimal, Decimal]],
    start_lat: Decimal,
    start_lon: Decimal,
    *,
    k: int = 6,
    max_spread_km: Optional[float] = None,  # None = pas de contrainte de dispersion
    hard_radius_km: float = 0.0,  # 0 = pas de filtre dur
) -> List[FrontClient]:
    """
    Sélectionne jusqu'à k clients par 'plus proche voisin' en partant du départ.
    Coût = distance Haversine.
    Optionnel: rejette un candidat s'il est à plus de `max_spread_km` de
    n'importe quel point déjà sélectionné (dispersion pairwise).
    """

    R = RouteOptimizationService

    if not points:
        return []

    def within_radius_from_start(lat, lon) -> bool:
        if hard_radius_km and hard_radius_km > 0:
            return (
                R.calculate_distance(start_lat, start_lon, lat, lon)
                <= float(hard_radius_km)
            )
        return True

    # filtre dur autour du départ si demandé
    remaining = [
        (c, lat, lon) for (c, lat, lon) in points if within_radius_from_start(lat, lon)
    ]
    if not remaining:
        remaining = points[:]  # fallback si on a tout exclu

    chosen: List[Tuple[FrontClient, Decimal, Decimal]] = []
    cur_lat, cur_lon = start_lat, start_lon

    while remaining and len(chosen) < k:
        # 1) tri par coût croissant (distance Haversine)
        dist = [
            R.calculate_distance(cur_lat, cur_lon, lat, lon)
            for (_, lat, lon) in remaining
        ]
        order = list(range(len(remaining)))
        order.sort(key=lambda i: dist[i])

        # 3) prendre le premier candidat qui respecte la dispersion (si demandée)
        picked_idx = None
        for i in order:
            cand = remaining[i]
            if max_spread_km is not None and max_spread_km > 0 and chosen:
                ok = True
                for (_, la, lo) in chosen:
                    if (
                        R.calculate_distance(la, lo, cand[1], cand[2])
                        > float(max_spread_km)
                    ):
                        ok = False
                        break
                if not ok:
                    continue
            picked_idx = i
            break

        if picked_idx is None:
            # aucun ne passe la dispersion : on relâche en ignorant la contrainte
            picked_idx = order[0]

        c = remaining.pop(picked_idx)
        chosen.append(c)
        cur_lat, cur_lon = c[1], c[2]

    return [c for (c, _, __) in chosen]


# --- Sélection locale robuste (conservée pour compatibilité)
# (rayon progressif autour du départ + contrainte d'écart max entre points)
def _select_local_group(
    points: List[Tuple[FrontClient, Decimal, Decimal]],
    start_lat: Decimal,
    start_lon: Decimal,
    *,
    k: int = 6,
    base_radius_km: float = 10.0,
    max_spread_km: float = 35.0,
    hard_radius_km: float = 0.0,
) -> List[FrontClient]:
    """Construit un groupe compact de `k` clients au plus proche du départ."""
    def d(a_lat, a_lon, b_lat, b_lon) -> float:
        return RouteOptimizationService.calculate_distance(a_lat, a_lon, b_lat, b_lon)

    limit = float(hard_radius_km) if hard_radius_km and hard_radius_km > 0 else 9999.0
    r = max(0.1, float(base_radius_km) or 10.0)

    # Étape 1 : rayon progressif
    while r <= limit + 1e-6:
        cand = [
            (c, lat, lon)
            for (c, lat, lon) in points
            if d(start_lat, start_lon, lat, lon) <= r
        ]
        if len(cand) >= min(k, len(points)):
            # Étape 2 : tri par distance au départ puis construction avec contrainte d'écart max
            cand.sort(key=lambda t: d(start_lat, start_lon, t[1], t[2]))

            def build_group(
                spread_km: float,
            ) -> List[Tuple[FrontClient, Decimal, Decimal]]:
                group: List[Tuple[FrontClient, Decimal, Decimal]] = []
                for item in cand:
                    if len(group) >= k:
                        break
                    if not group:
                        group.append(item)
                        continue
                    ok = True
                    for (_, la, lo) in group:
                        if d(la, lo, item[1], item[2]) > spread_km:
                            ok = False
                            break
                    if ok:
                        group.append(item)
                return group

            group = build_group(float(max_spread_km) or 35.0)
            relax = float(max_spread_km) or 35.0
            while len(group) < min(k, len(cand)) and relax < 200.0:
                relax += 5.0
                group = build_group(relax)
            if len(group) < min(k, len(cand)):
                group = cand[:k]
            return [c for (c, _, __) in group]

        r = min(limit, r * 1.5)

    # Fallback global : k plus proches du départ
    pool = sorted(points, key=lambda t: d(start_lat, start_lon, t[1], t[2]))
    return [c for (c, _, __) in pool[:k]]


def ensure_visits_next_4_weeks(
    run_date: Optional[date] = None, *, dry_run: bool = False, collect_breakdown: bool = True
) -> dict:
    """Complète la planification jusqu'à J+28.

    - 6 RDV/jour/commercial (max)
    - Jours ouvrés uniquement (WE/feriés exclus)
    - Créneau par défaut 09:00
    - Idempotent via get_or_create

    CHANGEMENT CLÉ :
    ➜ On construit un groupe *par jour* en partant du point de départ (greedy
      "plus proche voisin" + grappe compacte via Haversine), parmi les clients
      qui ont encore des visites à faire dans l'horizon.
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

    business_days = list(_iter_business_days(start, end))

    for commercial in Commercial.objects.all():
        if commercial.is_absent:
            skipped_absence += 1
            continue

        if collect_breakdown and commercial.id not in per_commercial_per_day:
            per_commercial_per_day[commercial.id] = {}

        start_coords = _get_commercial_start(commercial)
        s_lat = s_lon = None
        if start_coords:
            s_lat, s_lon = start_coords

        # --- pool de clients actifs + coordonnées ---
        clients_all = list(
            FrontClient.objects.filter(commercial_id=commercial.id, actif=True)
        )
        points_by_client: Dict[int, Tuple[FrontClient, Decimal, Decimal]] = {}
        for c in clients_all:
            coords = _get_first_client_coords(c)
            if coords:
                points_by_client[c.id] = (c, coords[0], coords[1])

        if not points_by_client:
            continue

        # --- besoins ("manquants") par client sur l'horizon ---
        need_remaining: Dict[int, int] = {}
        annee = start.year
        for cid, (cli, _, __) in points_by_client.items():
            objectif_annuel = _get_objectif_annuel(cli, commercial, annee)
            visites_valides = _get_visites_valides_annee(cli, commercial, annee)
            reste_annuel = max(0, objectif_annuel - visites_valides)

            classement = (cli.classement_client or "").upper().strip()

            # Améliorer la reconnaissance des classements avec couleurs
            if classement.startswith("A "):
                classement_normalise = "A"
            elif classement.startswith("B "):
                classement_normalise = "B"
            elif classement.startswith("C "):
                classement_normalise = "C"
            else:
                classement_normalise = classement

            cible_28 = CLASSEMENT_TO_TARGET_28D.get(classement_normalise, 1)

            # NOUVEAU : Si l'objectif annuel est atteint, on recommence avec la cible 28 jours
            if reste_annuel <= 0:
                # Client a atteint son objectif annuel, on peut recommencer avec la cible 28 jours
                cible_28_effective = cible_28
            else:
                cible_28_effective = min(cible_28, reste_annuel)

            deja_planifies = _get_already_planned_in_horizon(
                cli, commercial, start, end
            )
            manquants = max(0, cible_28_effective - deja_planifies)
            if manquants > 0:
                need_remaining[cid] = manquants
            else:
                skipped_objectif_zero += 1

        if not need_remaining:
            continue

        # Paramètres géo
        max_radius_km = float(getattr(settings, "MAX_RADIUS_KM", 0) or 0)
        # nouvel algo "par zone"
        same_day_spread_km = float(
            getattr(settings, "SAME_DAY_SPREAD_KM", 20.0) or 20.0
        )
        seed_limit = int(
            getattr(settings, "SAME_DAY_CLUSTER_SEED_LIMIT", 60) or 60
        )

        # --- Anti-doublon *horizon* (par nom normalisé) ---
        existing_horizon = (
            Rendezvous.objects.filter(
                commercial=commercial, date_rdv__gte=start, date_rdv__lte=end
            )
            .exclude(statut_rdv="annule")
            .select_related("client")
        )
        horizon_seen_names = {
            _norm_name_from_client(r.client)
            for r in existing_horizon
            if r.client
        }

        # --- boucle par jour ouvré ---
        for d in business_days:
            created_today = False  # ne réordonne que si l'on a réellement créé des RDV ce jour
            capacity = max(
                0,
                6
                - _count_rdv_non_annules_for_commercial_on_date(
                    commercial, d
                ),
            )
            if capacity <= 0:
                skipped_quota += 1
                continue

            # candidats pour CE JOUR (besoin > 0, pas déjà posé ce jour)
            day_candidates: List[Tuple[FrontClient, Decimal, Decimal]] = []
            for cid, need in need_remaining.items():
                if need <= 0:
                    continue
                cli, lat, lon = points_by_client[cid]
                if _rdv_exists_for_client_on_date(cli, commercial, d):
                    skipped_existing += 1
                    continue
                if start_coords and max_radius_km > 0:
                    if (
                        RouteOptimizationService.calculate_distance(
                            s_lat, s_lon, lat, lon
                        )
                        > max_radius_km
                    ):
                        continue

                # *** blocage horizon par nom ***
                if _norm_name_from_client(cli) in horizon_seen_names:
                    continue

                day_candidates.append((cli, lat, lon))

            if not day_candidates:
                continue

            # Déduplication par nom normalisé : on garde (si départ connu) le plus proche du départ
            if start_coords:

                def _dist_from_start(item):
                    return RouteOptimizationService.calculate_distance(
                        s_lat, s_lon, item[1], item[2]
                    )

            by_name: Dict[str, Tuple[FrontClient, Decimal, Decimal]] = {}
            for it in day_candidates:
                key = _norm_name_from_client(it[0])
                best = by_name.get(key)
                if best is None:
                    by_name[key] = it
                else:
                    if start_coords and _dist_from_start(it) < _dist_from_start(
                        best
                    ):
                        by_name[key] = it
            day_candidates = list(by_name.values())
            if not day_candidates:
                continue

            k = min(capacity, len(day_candidates))

            # --- Sélection par grappe stricte (toutes paires <= spread_km) ---
            if start_coords:
                seed_lat, seed_lon = s_lat, s_lon
            else:
                seed_lat, seed_lon = day_candidates[0][1], day_candidates[0][2]

            # Construire une grappe compacte de k points autour d'un centre
            pool = day_candidates
            selected_clients = _pick_k_zone_cluster(
                pool,
                Decimal(seed_lat),
                Decimal(seed_lon),
                k=k,
                spread_km=float(same_day_spread_km) or 20.0,
                seed_limit=int(seed_limit),
            )

            # Fallback si on n'arrive pas à obtenir k clients (relâchement progressif)
            relax = float(same_day_spread_km) or 20.0
            while len(selected_clients) < min(k, len(pool)) and relax < 50.0:
                relax += 5.0
                selected_clients = _pick_k_zone_cluster(
                    pool,
                    Decimal(seed_lat),
                    Decimal(seed_lon),
                    k=k,
                    spread_km=relax,
                    seed_limit=60,
                )

            # --- préparation anti-doublons "même nom" pour le jour d ---
            existing_today = (
                Rendezvous.objects.filter(commercial=commercial, date_rdv=d)
                .exclude(statut_rdv="annule")
                .select_related("client")
            )
            seen_names = {
                _norm_name_from_client(r.client)
                for r in existing_today
                if r.client
            }

            # --- création des RDV pour le jour d ---
            for client in selected_clients:
                if need_remaining.get(client.id, 0) <= 0:
                    continue

                name_key = _norm_name_from_client(client)
                # blocage intra-jour ET blocage horizon
                if name_key in seen_names or name_key in horizon_seen_names:
                    continue  # déjà présent

                if dry_run:
                    created_count += 1
                    need_remaining[client.id] -= 1
                    capacity -= 1
                    seen_names.add(name_key)
                    horizon_seen_names.add(
                        name_key
                    )  # important aussi en dry_run pour la logique locale
                    if collect_breakdown:
                        per_day[d.isoformat()] = (
                            per_day.get(d.isoformat(), 0) + 1
                        )
                        per_commercial_per_day[commercial.id][
                            d.isoformat()
                        ] = (
                            per_commercial_per_day[commercial.id].get(
                                d.isoformat(), 0
                            )
                            + 1
                        )
                    created_today = True
                    if capacity <= 0:
                        break
                    continue

                with transaction.atomic():
                    # IMPORTANT: ne pas inclure heure_rdv dans les critères -> évite les doublons
                    obj, created = Rendezvous.objects.get_or_create(
                        client=client,
                        commercial=commercial,
                        date_rdv=d,
                        defaults={
                            "heure_rdv": dtime(hour=9, minute=0),
                            "statut_rdv": "a_venir",
                            "objet": "",
                        },
                    )
                    if created:
                        # contrôle distance journalière estimée (après insertion)
                        max_daily_km = float(
                            getattr(
                                settings, "MAX_DAILY_DISTANCE_KM", 0
                            )
                            or 0
                        )
                        if max_daily_km > 0:
                            est = _estimate_day_distance_km(commercial, d)
                            if est > max_daily_km:
                                obj.delete()
                                continue
                        created_count += 1
                        need_remaining[client.id] -= 1
                        capacity -= 1
                        seen_names.add(name_key)
                        horizon_seen_names.add(
                            name_key
                        )  # <-- ajoute au set horizon
                        if collect_breakdown:
                            per_day[d.isoformat()] = (
                                per_day.get(d.isoformat(), 0) + 1
                            )
                            per_commercial_per_day[commercial.id][
                                d.isoformat()
                            ] = (
                                per_commercial_per_day[commercial.id].get(
                                    d.isoformat(), 0
                                )
                                + 1
                            )
                        created_today = True
                    else:
                        skipped_existing += 1

                if capacity <= 0:
                    break

            # réordonne les créneaux du jour UNIQUEMENT si on a créé quelque chose
            if created_today:
                try:
                    RouteOptimizationService.reorder_day_assign_slots(
                        commercial, d
                    )
                except Exception:
                    logger.exception("Reorder failed for %s %s", commercial, d)

    return {
        "created": created_count,
        "skipped_absent_commercials": skipped_absence,
        "skipped_quota_days": skipped_quota,
        "skipped_existing": skipped_existing,
        "skipped_objectif_zero": skipped_objectif_zero,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "per_day": per_day if collect_breakdown else None,
        "per_commercial_per_day": per_commercial_per_day
        if collect_breakdown
        else None,
    }



# ==========================================================
# Google Distance Matrix — fonction réutilisable (module-level)
# ==========================================================
def google_distance_matrix_one_to_many(
    origin,
    destinations,
    *,
    mode=None,
    timeout=15,
    rate_limit=None,
    chunk_size=25,
):
    """
    Appelle Google Distance Matrix pour 1 origine -> N destinations.

    Retour:
      - None si clé absente / erreur globale API
      - sinon liste alignée sur destinations:
        [{"status":"OK","distance_m":123,"duration_s":456}, ...]
    """
    import requests
    from django.conf import settings

    key = (getattr(settings, "GOOGLE_MAPS_API_KEY", "") or "").strip()
    if not key or not destinations:
        return None

    travel_mode = (mode or getattr(settings, "GOOGLE_MAPS_TRAVEL_MODE", "driving") or "driving")
    max_dests = int(chunk_size or 25)
    max_dests = max(1, min(max_dests, 25))

    origin_str = f"{origin[0]},{origin[1]}"

    def _call(chunk):
        dest_str = "|".join(f"{lat},{lon}" for (lat, lon) in chunk)
        params = {
            "origins": origin_str,
            "destinations": dest_str,
            "mode": travel_mode,
            "units": "metric",
            "key": key,
        }
        if callable(rate_limit):
            rate_limit()

        r = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params=params,
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("status") != "OK":
            logger.warning(
                "Google Distance Matrix status != OK: %s | %s",
                data.get("status"),
                data.get("error_message"),
            )
            return None

        rows = data.get("rows") or []
        if not rows:
            return None

        els = (rows[0].get("elements") or [])
        if len(els) != len(chunk):
            return None

        out = []
        for el in els:
            st = el.get("status")
            if st == "OK":
                out.append({
                    "status": "OK",
                    "distance_m": int(el["distance"]["value"]),
                    "duration_s": int(el["duration"]["value"]),
                })
            else:
                out.append({"status": st or "UNKNOWN", "distance_m": None, "duration_s": None})
        return out

    out_all = []
    for i in range(0, len(destinations), max_dests):
        chunk = destinations[i:i+max_dests]
        res = _call(chunk)
        if res is None:
            return None
        out_all.extend(res)

    return out_all


# ==========================================================
# Google Distance Matrix — many-to-many (module-level)
# ==========================================================
def google_distance_matrix_many_to_many(
    origins,
    destinations,
    *,
    mode=None,
    timeout=15,
    max_origins=25,
    max_destinations=25,
    max_elements=100,
    retry_over_query=2,
    backoff_sec=1.0,
):
    """
    Appelle Google Distance Matrix pour M origines -> N destinations, en chunkant automatiquement.

    Retour:
      matrix[M][N] = {"status": str, "distance_m": int|None, "duration_s": int|None, "error_message": str|None}

    Notes:
    - Google renvoie MAX_DIMENSIONS_EXCEEDED si >25 origines ou >25 destinations. :contentReference[oaicite:0]{index=0}
    - Google renvoie MAX_ELEMENTS_EXCEEDED si le produit origines*dest dépasse la limite par requête. :contentReference[oaicite:1]{index=1}
    """
    import time as _time
    import requests as _requests
    from django.conf import settings as _settings

    key = (getattr(_settings, "GOOGLE_MAPS_API_KEY", "") or "").strip()
    if not key or not origins or not destinations:
        return []

    mode = mode or getattr(_settings, "GOOGLE_MAPS_TRAVEL_MODE", "driving")

    # Configurable via settings si tu veux
    max_origins = int(getattr(_settings, "GOOGLE_DM_MAX_ORIGINS", max_origins) or max_origins)
    max_destinations = int(getattr(_settings, "GOOGLE_DM_MAX_DESTINATIONS", max_destinations) or max_destinations)
    max_elements = int(getattr(_settings, "GOOGLE_DM_MAX_ELEMENTS", max_elements) or max_elements)

    M, N = len(origins), len(destinations)
    out = [[{"status": "PENDING", "distance_m": None, "duration_s": None, "error_message": None} for _ in range(N)] for __ in range(M)]

    def _fmt(points):
        return "|".join(f"{float(lat)},{float(lon)}" for (lat, lon) in points)

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    oi = 0
    while oi < M:
        o_chunk = origins[oi : oi + max_origins]

        # Pour respecter max_elements: d_step <= floor(max_elements / len(o_chunk))
        d_step = max(1, min(max_destinations, max_elements // max(1, len(o_chunk))))

        di = 0
        while di < N:
            d_chunk = destinations[di : di + d_step]

            params = {
                "origins": _fmt(o_chunk),
                "destinations": _fmt(d_chunk),
                "mode": mode,
                "units": "metric",
                "key": key,
            }

            attempt = 0
            while True:
                try:
                    resp = _requests.get(url, params=params, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    status = data.get("status")

                    if status == "OVER_QUERY_LIMIT" and attempt < retry_over_query:
                        attempt += 1
                        _time.sleep(backoff_sec * attempt)
                        continue

                    if status != "OK":
                        # On marque toute la sous-matrice en erreur
                        for r in range(len(o_chunk)):
                            for c in range(len(d_chunk)):
                                out[oi + r][di + c] = {
                                    "status": status or "ERROR",
                                    "distance_m": None,
                                    "duration_s": None,
                                    "error_message": data.get("error_message"),
                                }
                        break

                    rows = data.get("rows", [])
                    for r, row in enumerate(rows):
                        elems = row.get("elements", [])
                        for c, el in enumerate(elems):
                            el_status = el.get("status")
                            if el_status == "OK":
                                out[oi + r][di + c] = {
                                    "status": "OK",
                                    "distance_m": int(el["distance"]["value"]),
                                    "duration_s": int(el["duration"]["value"]),
                                    "error_message": None,
                                }
                            else:
                                out[oi + r][di + c] = {
                                    "status": el_status or "ERROR",
                                    "distance_m": None,
                                    "duration_s": None,
                                    "error_message": el.get("error_message") or data.get("error_message"),
                                }
                    break

                except Exception as e:
                    for r in range(len(o_chunk)):
                        for c in range(len(d_chunk)):
                            out[oi + r][di + c] = {
                                "status": "EXCEPTION",
                                "distance_m": None,
                                "duration_s": None,
                                "error_message": str(e),
                            }
                    break

            di += d_step

        oi += max_origins

    return out
