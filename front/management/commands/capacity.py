from django.core.management.base import BaseCommand, CommandError
from datetime import date
from front.utils import business_days_in_month, monthly_rdv_capacity


class Command(BaseCommand):
    help = "Affiche les jours ouvrés et la capacité de RDV du mois (quota/jour configurable)."

    def add_arguments(self, parser):
        today = date.today()
        parser.add_argument('--year', type=int, default=today.year, help='Année (ex: 2025)')
        parser.add_argument('--month', type=int, default=today.month, help='Mois (1-12)')
        parser.add_argument('--daily-quota', type=int, default=6, help='Nombre de RDV par jour (par commercial)')
        parser.add_argument('--cap-to-four-weeks', action='store_true', help='Borne à 4 semaines ouvrées (20 jours max)')

    def handle(self, *args, **options):
        year = options['year']
        month = options['month']
        quota = options['daily_quota']
        cap4 = options['cap_to_four_weeks']

        if month < 1 or month > 12:
            raise CommandError('--month doit être entre 1 et 12')
        if year < 1900 or year > 3000:
            raise CommandError('--year invalide')

        wd = business_days_in_month(year, month)
        cap = monthly_rdv_capacity(year, month, daily_quota=quota, cap_to_four_weeks=cap4)

        self.stdout.write(self.style.SUCCESS(
            f"Mois {year}-{month:02d}: {wd} jours ouvrés, capacité = {cap} (quota={quota}{', borne 4 semaines' if cap4 else ''})"
        ))


