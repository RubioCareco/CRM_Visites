from django.core.management.base import BaseCommand
from front.services import GeocodingService
from front.models import Adresse

class Command(BaseCommand):
    help = "Géocode les 5 premières adresses sans coordonnées (test)"

    def handle(self, *args, **options):
        adresses = Adresse.objects.filter(latitude__isnull=True, longitude__isnull=True)[:5]
        self.stdout.write(self.style.SUCCESS(f"{adresses.count()} adresses à géocoder (échantillon)"))
        for adresse in adresses:
            if adresse.adresse and adresse.code_postal and adresse.ville:
                coords = GeocodingService.geocode_address(adresse.adresse, adresse.code_postal, adresse.ville)
                if coords:
                    adresse.latitude, adresse.longitude = coords
                    adresse.geocode_date = None
                    adresse.save()
                    self.stdout.write(self.style.SUCCESS(f"Géocodé: {adresse} -> {coords}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Échec géocodage: {adresse}"))
            else:
                self.stdout.write(self.style.WARNING(f"Adresse incomplète: {adresse}")) 