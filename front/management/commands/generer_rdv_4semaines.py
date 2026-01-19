from datetime import date, timedelta

from django.core.management.base import BaseCommand
from front.models import Commercial, Rendezvous
from front.utils import generer_rendezvous_simples, is_jour_ferie_france


class Command(BaseCommand):
    help = (
        "Génère 6 RDV par jour ouvré pour chaque commercial actif "
        "sur une période de N semaines (défaut : 4) à partir d'aujourd'hui."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=4,
            help="Nombre de semaines à couvrir (défaut : 4)",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Limiter à un seul commercial (email). Par défaut : tous les commerciaux.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Supprime les RDV 'a_venir' déjà existants sur ces jours avant de régénérer.",
        )

    def handle(self, *args, **options):
        weeks = options["weeks"]
        start_date = date.today()
        end_date = start_date + timedelta(weeks=weeks) - timedelta(days=1)

        qs = Commercial.objects.filter(role="commercial")
        if options["email"]:
            qs = qs.filter(email=options["email"])

        commerciaux = list(qs)
        if not commerciaux:
            self.stdout.write(self.style.WARNING("Aucun commercial trouvé."))
            return

        self.stdout.write(
            f"Période : du {start_date} au {end_date} ({weeks} semaines)"
        )
        self.stdout.write(
            "Commerciaux : " + ", ".join(f"{c.id}-{c.email}" for c in commerciaux)
        )

        total_rdv = 0
        current = start_date

        while current <= end_date:
            # Sauter week-ends et jours fériés
            if current.weekday() >= 5 or is_jour_ferie_france(current):
                current += timedelta(days=1)
                continue

            for commercial in commerciaux:
                qs_rdv = Rendezvous.objects.filter(
                    commercial=commercial,
                    date_rdv=current,
                    statut_rdv="a_venir",
                )

                if options["force"]:
                    deleted = qs_rdv.count()
                    if deleted:
                        qs_rdv.delete()
                        self.stdout.write(
                            f"[{current}] {commercial.email}: {deleted} RDV supprimés (force)"
                        )
                else:
                    # Si on ne force pas et qu'il y a déjà des RDV → on ne touche pas
                    if qs_rdv.exists():
                        continue

                # 👉 Réutilisation directe de ta logique actuelle
                created = generer_rendezvous_simples(
                    date_cible=current,
                    commercial=commercial,
                )

                if created:
                    self.stdout.write(
                        f"[{current}] {commercial.email}: {created} RDV créés"
                    )
                    total_rdv += created

            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Total RDV créés : {total_rdv}"))
