from django.core.management.base import BaseCommand
from front.models import SatisfactionB2B

class Command(BaseCommand):
    help = "Recalcule et met à jour tous les scores hybrides de SatisfactionB2B selon la logique actuelle."

    def handle(self, *args, **options):
        total = SatisfactionB2B.objects.count()
        updated = 0
        for s in SatisfactionB2B.objects.all():
            s.save()  # Déclenche le recalcul du score hybride
            updated += 1
            if updated % 100 == 0:
                self.stdout.write(f"{updated}/{total} scores recalculés...")
        self.stdout.write(self.style.SUCCESS(f"Mise à jour terminée : {updated} scores hybrides recalculés.")) 