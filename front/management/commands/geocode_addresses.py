from django.core.management.base import BaseCommand
from front.services import GeocodingService


class Command(BaseCommand):
    help = 'Géocode toutes les adresses qui n\'ont pas encore de coordonnées'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Début du géocodage des adresses...')
        )
        
        try:
            GeocodingService.geocode_all_addresses()
            self.stdout.write(
                self.style.SUCCESS('Géocodage terminé avec succès !')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erreur lors du géocodage: {e}')
            ) 