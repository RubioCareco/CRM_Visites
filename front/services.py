import requests
import time
from typing import List, Tuple, Optional
from decimal import Decimal
from django.utils import timezone
from .models import Adresse, Commercial, Rendezvous


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