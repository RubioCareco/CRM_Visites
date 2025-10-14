from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta, time
from front.models import Commercial, FrontClient, Rendezvous
from front.utils import generer_rendezvous_simples, is_jour_ferie_france


class Command(BaseCommand):
    help = "Génère automatiquement 6 RDV par jour pour tout le mois pour chaque commercial"

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            help='Mois au format YYYY-MM (ex: 2025-01). Par défaut: mois en cours'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer la régénération même si des RDV existent déjà'
        )

    def handle(self, *args, **options):
        # Déterminer le mois cible
        if options['month']:
            try:
                year, month = map(int, options['month'].split('-'))
                target_date = date(year, month, 1)
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Format de mois invalide. Utilisez YYYY-MM (ex: 2025-01)')
                )
                return
        else:
            # Mois en cours
            today = date.today()
            target_date = date(today.year, today.month, 1)

        # Calculer le dernier jour du mois
        if target_date.month == 12:
            next_month = date(target_date.year + 1, 1, 1)
        else:
            next_month = date(target_date.year, target_date.month + 1, 1)
        last_day = next_month - timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f'Génération des RDV pour {target_date.strftime("%B %Y")}')
        )

        total_rdv_crees = 0
        commerciaux = Commercial.objects.filter(role='commercial')

        for commercial in commerciaux:
            self.stdout.write(f'\n--- Commercial: {commercial.commercial} ---')
            rdv_commercial = 0

            # Parcourir chaque jour du mois
            current_date = target_date
            while current_date <= last_day:
                # Vérifier si c'est un jour ouvré (pas week-end, pas férié)
                if current_date.weekday() < 5 and not is_jour_ferie_france(current_date):
                    # Vérifier s'il y a déjà des RDV pour ce jour
                    rdv_existants = Rendezvous.objects.filter(
                        commercial=commercial,
                        date_rdv=current_date,
                        statut_rdv='a_venir'
                    ).count()

                    if rdv_existants == 0 or options['force']:
                        # Supprimer les RDV existants si force
                        if options['force'] and rdv_existants > 0:
                            Rendezvous.objects.filter(
                                commercial=commercial,
                                date_rdv=current_date,
                                statut_rdv='a_venir'
                            ).delete()
                            self.stdout.write(f'  {current_date}: {rdv_existants} RDV supprimés')

                        # Générer 6 RDV pour ce jour
                        rdv_jour = generer_rendezvous_simples(current_date)
                        if rdv_jour > 0:
                            self.stdout.write(
                                self.style.SUCCESS(f'  {current_date}: {rdv_jour} RDV créés')
                            )
                            rdv_commercial += rdv_jour
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'  {current_date}: Aucun RDV créé')
                            )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  {current_date}: {rdv_existants} RDV existent déjà')
                        )
                else:
                    self.stdout.write(f'  {current_date}: Week-end ou jour férié')

                current_date += timedelta(days=1)

            self.stdout.write(
                self.style.SUCCESS(f'Total {commercial.commercial}: {rdv_commercial} RDV')
            )
            total_rdv_crees += rdv_commercial

        self.stdout.write(
            self.style.SUCCESS(f'\n🎯 Génération terminée ! Total: {total_rdv_crees} RDV créés')
        )

        # Instructions pour l'utilisation
        self.stdout.write('\n📋 Pour automatiser cette commande :')
        self.stdout.write('1. Ajouter dans crontab (Linux/Mac) :')
        self.stdout.write('   0 1 1 * * cd /path/to/project && python manage.py generer_rdv_mensuel')
        self.stdout.write('2. Ou utiliser Windows Task Scheduler pour exécuter :')
        self.stdout.write('   python manage.py generer_rdv_mensuel') 