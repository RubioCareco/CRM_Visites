from django.core.management.base import BaseCommand
from front.models import Rendezvous

class Command(BaseCommand):
    help = "Remplit le champ rs_nom de tous les Rendezvous existants à partir du client lié."

    def handle(self, *args, **options):
        count = 0
        for rdv in Rendezvous.objects.all():
            client = rdv.client
            if client:
                rs_nom = getattr(client, 'rs_nom', None) or getattr(client, 'nom', None) or ''
                if rdv.rs_nom != rs_nom:
                    rdv.rs_nom = rs_nom
                    rdv.save(update_fields=['rs_nom'])
                    count += 1
        self.stdout.write(self.style.SUCCESS(f"Champ rs_nom mis à jour pour {count} rendez-vous.")) 