from django.core.management.base import BaseCommand
from datetime import date, timedelta
from front.models import Commercial, Rendezvous


class Command(BaseCommand):
    help = "Réduit à un maximum de N RDV 'a_venir' par jour et par commercial (garde les plus tôt)."

    def add_arguments(self, parser):
        parser.add_argument('--daily-quota', type=int, default=6, help='Quota max par jour (défaut: 6)')
        parser.add_argument('--days', type=int, default=35, help="Nombre de jours à parcourir depuis aujourd'hui (défaut: 35)")

    def handle(self, *args, **options):
        quota = max(0, int(options['daily_quota']))
        horizon_days = max(1, int(options['days']))

        start = date.today()
        end = start + timedelta(days=horizon_days)
        changed = 0

        for commercial in Commercial.objects.all():
            d = start
            while d <= end:
                qs = (Rendezvous.objects
                      .filter(commercial=commercial, date_rdv=d, statut_rdv='a_venir')
                      .order_by('heure_rdv', 'id'))
                count = qs.count()
                if count > quota:
                    # supprimer les plus tardifs (au-delà du quota)
                    to_delete = list(qs[quota:])
                    ids = [r.id for r in to_delete]
                    Rendezvous.objects.filter(id__in=ids).delete()
                    changed += len(ids)
                d += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Cap appliqué: quota={quota}, RDV supprimés={changed}"))


