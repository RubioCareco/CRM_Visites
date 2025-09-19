from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from datetime import date
from front.models import Commercial
from front.services import RouteOptimizationService


class Command(BaseCommand):
    help = "Affiche l'itinéraire optimisé (ordre, distances/durées) pour un commercial et une date"

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None, help='Date au format YYYY-MM-DD (défaut: aujourd\'hui)')
        parser.add_argument('--commercial', type=str, required=True, help='Nom affiché du commercial (ex: "Commercial 2")')

    def handle(self, *args, **options):
        target_date = options['date']
        try:
            if target_date:
                yyyy, mm, dd = [int(x) for x in target_date.split('-')]
                d = date(yyyy, mm, dd)
            else:
                d = date.today()
        except Exception:
            raise CommandError("--date doit être au format YYYY-MM-DD")

        name = options['commercial']
        commercial = Commercial.objects.filter(commercial__iexact=name).first()
        if not commercial:
            # tenter variantes simples (ex: COMMERCIAL1)
            commercial = Commercial.objects.filter(Q(commercial__iexact=name) | Q(nom__iexact=name)).first()
        if not commercial:
            raise CommandError(f"Commercial introuvable: {name}")

        result = RouteOptimizationService.get_optimized_route_for_commercial(commercial, d.isoformat())

        rdvs = result.get('rdvs', [])
        if not rdvs:
            self.stdout.write(self.style.WARNING("Aucun RDV à afficher pour cette date."))
            return

        mode = result.get('mode') or 'N/A'
        self.stdout.write(self.style.SUCCESS(f"Itinéraire optimisé pour {commercial} le {d} (mode: {mode}):"))
        for idx, rdv in enumerate(rdvs, 1):
            client = getattr(rdv, 'client', None)
            rs = getattr(client, 'rs_nom', 'N/A') if client else 'N/A'
            self.stdout.write(f"{idx}. {rs} à {rdv.heure_rdv.strftime('%H:%M') if rdv.heure_rdv else '??:??'}")

        details = result.get('route_details', [])
        if details:
            self.stdout.write("")
            self.stdout.write("Segments:")
            for i, seg in enumerate(details, 1):
                km = round(seg['distance_from_previous'], 2)
                client = getattr(seg['rdv'], 'client', None)
                rs = getattr(client, 'rs_nom', 'N/A') if client else 'N/A'
                self.stdout.write(f" -> {i}) {rs}: +{km} km")

        total_km = result.get('total_distance', 0)
        total_min = result.get('estimated_time_minutes', 0)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Total: {total_km} km ~ {total_min} min"))


