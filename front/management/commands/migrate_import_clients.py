from django.core.management.base import BaseCommand
from front.models import ImportClientCorrected, FrontClient, Adresse

class Command(BaseCommand):
    help = "Migre les données de import_clients_corrected vers front_client et adresse."

    def handle(self, *args, **options):
        count = 0
        for ic in ImportClientCorrected.objects.all():
            print(f"Client: {ic.rs_nom} - Commercial: {ic.commercial}")
            # Création du client
            client = FrontClient.objects.create(
                civilite=ic.civilite,
                code_comptable=ic.code_comptable,
                email=ic.e_mail,
                email_comptabilite=ic.e_mail_comptabilité,
                en_compte=str(ic.en_compte).strip() == "1",
                prenom=ic.prénom,
                rs_nom=ic.rs_nom,
                statut=ic.statut,
                telephone=ic.telephone,
                actif=getattr(ic, 'actif', True),
                commercial=ic.commercial,
            )
            # Création de l'adresse liée
            Adresse.objects.create(
                client=client,
                adresse=ic.adresse,
                code_postal=getattr(ic, 'code_postal', None),
                ville=ic.ville
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} clients et adresses migrés avec succès !")) 