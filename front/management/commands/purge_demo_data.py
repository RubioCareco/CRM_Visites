from django.core.management.base import BaseCommand
from django.db import transaction

from front.models import (
    SatisfactionB2B,
    CommentaireRdv,
    ActivityLog,
    Rendezvous,
)


ORDERED_MODELS = [
    (SatisfactionB2B, "SatisfactionB2B"),
    (CommentaireRdv, "CommentaireRdv"),
    (ActivityLog, "ActivityLog"),
    (Rendezvous, "Rendezvous"),
]


class Command(BaseCommand):
    help = (
        "Purge les données (lignes) de démonstration: RDV, commentaires, logs, questionnaires. "
        "Ne modifie ni le schéma ni les tables. (ClientVisitStats est exclu)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche uniquement les volumes qui seraient supprimés.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Ne demande pas de confirmation avant suppression.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        assume_yes = options["yes"]

        counts = {}
        for model, label in ORDERED_MODELS:
            counts[label] = model.objects.count()

        self.stdout.write(self.style.NOTICE("\nVolumes actuels:"))
        for label, c in counts.items():
            self.stdout.write(f"  - {label}: {c}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry-run terminé. Aucune suppression effectuée."))
            return

        if not assume_yes:
            confirm = input(
                "\nConfirmer la suppression DEFINITIVE de ces données ? (oui/non): "
            ).strip().lower()
            if confirm not in {"oui", "o", "yes", "y"}:
                self.stdout.write(self.style.WARNING("Opération annulée."))
                return

        with transaction.atomic():
            # Respecter l'ordre pour éviter surprises de contrainte
            for model, label in ORDERED_MODELS:
                deleted, _ = model.objects.all().delete()
                self.stdout.write(f"Supprimé {deleted} lignes de {label}")

        self.stdout.write(self.style.SUCCESS("\nPurge terminée avec succès."))


