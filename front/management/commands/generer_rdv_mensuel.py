from datetime import date, timedelta

from django.core.management.base import BaseCommand

from front.models import Commercial, Rendezvous
from front.utils import generer_rendezvous_simples, is_jour_ferie_france


class Command(BaseCommand):
    help = (
        "Génère automatiquement 6 RDV 'a_venir' par jour pour un mois donné "
        "pour chaque commercial (jours ouvrés uniquement)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            type=str,
            help="Mois au format YYYY-MM (ex: 2025-01). Par défaut : mois en cours.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forcer la régénération même si des RDV 'a_venir' existent déjà.",
        )

    def handle(self, *args, **options):
        today = date.today()

        # 1) Déterminer le mois cible
        month_arg = options.get("month")
        if month_arg:
            try:
                year, month = map(int, month_arg.split("-"))
                target_date = date(year, month, 1)
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        "Format de mois invalide. Utilisez YYYY-MM (ex: 2025-01)."
                    )
                )
                return
        else:
            # Mois en cours
            target_date = date(today.year, today.month, 1)

        # 2) Calculer le dernier jour du mois
        if target_date.month == 12:
            next_month = date(target_date.year + 1, 1, 1)
        else:
            next_month = date(target_date.year, target_date.month + 1, 1)
        last_day = next_month - timedelta(days=1)

        # 3) Ne jamais générer dans le passé : on commence au max(1er du mois, aujourd'hui)
        start_date = max(target_date, today)

        self.stdout.write(
            self.style.SUCCESS(
                f"Génération des RDV pour {target_date.strftime('%B %Y')} "
                f"(du {start_date} au {last_day})."
            )
        )

        total_rdv_crees = 0
        commerciaux = Commercial.objects.filter(role="commercial")

        for commercial in commerciaux:
            self.stdout.write(f"\n--- Commercial : {commercial.commercial} ---")
            rdv_commercial = 0

            # 4) Parcourir chaque jour du mois, à partir d'aujourd'hui seulement
            current_date = start_date
            while current_date <= last_day:
                # Jours ouvrés uniquement (lundi–vendredi) + pas férié
                if current_date.weekday() < 5 and not is_jour_ferie_france(current_date):
                    rdv_existants = Rendezvous.objects.filter(
                        commercial=commercial,
                        date_rdv=current_date,
                        statut_rdv="a_venir",
                    ).count()

                    if rdv_existants == 0 or options.get("force"):
                        # Si --force, on supprime les RDV 'a_venir' existants avant de régénérer
                        if options.get("force") and rdv_existants > 0:
                            deleted, _ = Rendezvous.objects.filter(
                                commercial=commercial,
                                date_rdv=current_date,
                                statut_rdv="a_venir",
                            ).delete()
                            self.stdout.write(
                                f"  {current_date}: {deleted} RDV 'a_venir' supprimés (force)."
                            )

                        # 5) Générer les RDV pour CE commercial uniquement
                        rdv_jour = generer_rendezvous_simples(
                            date_cible=current_date,
                            commercial=commercial,
                        )

                        if rdv_jour > 0:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  {current_date}: {rdv_jour} RDV créés."
                                )
                            )
                            rdv_commercial += rdv_jour
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  {current_date}: aucun RDV créé "
                                    "(capacité atteinte ou pas de clients éligibles)."
                                )
                            )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  {current_date}: {rdv_existants} RDV 'a_venir' "
                                "existent déjà, rien fait."
                            )
                        )
                else:
                    self.stdout.write(f"  {current_date}: week-end ou jour férié, ignoré.")

                current_date += timedelta(days=1)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Total pour {commercial.commercial} : {rdv_commercial} RDV créés."
                )
            )
            total_rdv_crees += rdv_commercial

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎯 Génération terminée ! Total : {total_rdv_crees} RDV créés."
            )
        )
