import os
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from front.models import FrontClient, Rendezvous, Commercial, Adresse
from geopy.geocoders import Nominatim
from django.db.models import Q
import math

load_dotenv()

class Command(BaseCommand):
    help = "Planifie automatiquement 7 rendez-vous optimisés pour COMMERCIAL 1"

    def geocode_address_nominatim(self, address):
        geolocator = Nominatim(user_agent="crm_visites")
        location = geolocator.geocode(address)
        if location:
            return [location.longitude, location.latitude]
        return None

    def haversine_distance(self, lon1, lat1, lon2, lat2):
        R = 6371  # Rayon de la Terre en km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c * 1000  # en mètres

    def handle(self, *args, **options):
        # ORS supprimé: on s'appuie sur Haversine/Google dans les services

        # 2. Géocoder dynamiquement le point de départ avec Nominatim
        adresse_depart = "10 avenue Normandie Niémen, 64140 Lons"
        point_depart = self.geocode_address_nominatim(adresse_depart)
        if not point_depart:
            self.stdout.write(self.style.ERROR("Impossible de géocoder l'adresse de départ."))
            return
        self.stdout.write(self.style.SUCCESS(f"Coordonnées du point de départ : {point_depart}"))

        # 3. Récupérer les clients de COMMERCIAL 1 avec au moins une adresse géocodée (toutes variantes)
        clients = FrontClient.objects.filter(
            Q(commercial__iexact='COMMERCIAL1') |
            Q(commercial__iexact='Commercial 1') |
            Q(commercial__iexact='Yannick Commercial1')
        ).prefetch_related('adresses')

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

        self.stdout.write(self.style.SUCCESS(f"{len(points_a_visiter)} adresses géocodées trouvées pour COMMERCIAL 1 (toutes variantes)."))

        # 5. Utilisation de la distance Haversine pour optimiser la tournée
        max_haversine = 50
        if len(points_a_visiter) > max_haversine:
            points_haversine = points_a_visiter[:max_haversine]
            self.stdout.write(self.style.WARNING(f"Plus de 50 adresses, seules les 50 premières sont traitées pour la tournée."))
        else:
            points_haversine = points_a_visiter

        lon0, lat0 = point_depart
        for p in points_haversine:
            lon, lat = p['coords']
            p['distance_from_start'] = self.haversine_distance(lon0, lat0, lon, lat)

        points_haversine.sort(key=lambda x: x['distance_from_start'])
        tournee = points_haversine[:7]

        self.stdout.write(self.style.SUCCESS("\nTournée optimisée pour la matinée (Haversine) :"))
        for idx, rdv in enumerate(tournee, 1):
            self.stdout.write(f"{idx}. {rdv['client_nom']} - {rdv['adresse']} (distance : {rdv['distance_from_start']/1000:.2f} km)")
        total_distance = sum(rdv['distance_from_start'] for rdv in tournee)
        self.stdout.write(self.style.SUCCESS(f"Distance totale parcourue (départ -> 7 clients, à vol d'oiseau) : {total_distance/1000:.2f} km"))

        from datetime import datetime, time, date
        # Récupérer le commercial COMMERCIAL 1 (première variante trouvée)
        commercial_obj = Commercial.objects.filter(
            Q(commercial__iexact='COMMERCIAL1') |
            Q(commercial__iexact='Commercial 1') |
            Q(commercial__iexact='Yannick Commercial1')
        ).first()
        if not commercial_obj:
            self.stdout.write(self.style.ERROR("Aucun commercial 'COMMERCIAL 1' trouvé dans la base."))
            return

        # Créneaux horaires du matin (à déclarer ici pour éviter NameError)
        creneaux = [time(9,0), time(9,30), time(10,0), time(10,30), time(11,0), time(11,30), time(12,0)]
        today = date.today()

        rdv_crees = 0
        for idx, rdv in enumerate(tournee):
            if idx >= len(creneaux):
                break
            client_obj = FrontClient.objects.filter(id=rdv['client_id']).first()
            if not client_obj:
                self.stdout.write(self.style.WARNING(f"Client introuvable pour l'ID {rdv['client_id']}"))
                continue
            # Vérifier qu'il n'y a pas déjà un RDV à cette date/heure pour ce client/commercial
            existe = Rendezvous.objects.filter(
                client=client_obj,
                commercial=commercial_obj,
                date_rdv=today,
                heure_rdv=creneaux[idx]
            ).exists()
            if existe:
                self.stdout.write(self.style.WARNING(f"RDV déjà existant pour {client_obj.rs_nom} à {creneaux[idx]}"))
                continue
            Rendezvous.objects.create(
                client=client_obj,
                commercial=commercial_obj,
                date_rdv=today,
                heure_rdv=creneaux[idx],
                objet="",
                statut_rdv='a_venir',
                rs_nom=client_obj.rs_nom
            )
            self.stdout.write(self.style.SUCCESS(f"RDV créé pour {client_obj.rs_nom} à {creneaux[idx]}"))
            rdv_crees += 1
        self.stdout.write(self.style.SUCCESS(f"{rdv_crees} rendez-vous créés pour COMMERCIAL 1 le {today}"))
