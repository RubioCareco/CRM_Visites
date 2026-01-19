from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from front.services import ensure_visits_next_4_weeks


class Command(BaseCommand):
    help = "Génère/complète les rendez-vous pour avoir 4 semaines d'avance pour chaque commercial."

    def handle(self, *args, **options):
        env = getattr(settings, "ENV", "dev")

        self.stdout.write(self.style.WARNING(
            f"[ensure_next_4_weeks] Lancement (ENV={env}) à {timezone.now()}..."
        ))

        # Sécurité : on ne laisse tourner ça qu'en prod
        if env != "prod":
            self.stdout.write(self.style.ERROR(
                "[ensure_next_4_weeks] ENV != 'prod', arrêt (sécurité)."
            ))
            return

        try:
            result = ensure_visits_next_4_weeks()
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"[ensure_next_4_weeks] ERREUR pendant l'exécution : {e}"
            ))
            raise

        created = result.get("created") if isinstance(result, dict) else "?"
        self.stdout.write(self.style.SUCCESS(
            f"[ensure_next_4_weeks] Terminé, RDV créés: {created}."
        ))
