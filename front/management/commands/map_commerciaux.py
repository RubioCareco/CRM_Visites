from django.core.management.base import BaseCommand
from front.models import FrontClient, Commercial

class Command(BaseCommand):
    help = "Mappe les commerciaux aux clients en remplissant le champ commercial_id de FrontClient."

    def handle(self, *args, **options):
        def normalize(val):
            return (val or "").lower().replace(" ", "").replace("-", "")

        count = 0
        for client in FrontClient.objects.all():
            if client.commercial:
                client_norm = normalize(client.commercial)
                commercial = None
                for c in Commercial.objects.all():
                    if normalize(c.commercial) == client_norm:
                        commercial = c
                        break
                if commercial:
                    client.commercial_id = commercial.id
                    client.save()
                    count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} clients mis à jour avec leur commercial_id !")) 