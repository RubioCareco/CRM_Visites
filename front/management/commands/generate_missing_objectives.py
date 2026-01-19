from django.core.management.base import BaseCommand
from front.models import FrontClient, Commercial, ClientVisitStats
from django.utils import timezone

class Command(BaseCommand):
    help = 'Génère les objectifs annuels manquants pour tous les clients'

    def handle(self, *args, **options):
        current_year = timezone.now().year
        
        # Récupérer tous les commerciaux
        commerciaux = Commercial.objects.all()
        
        # Récupérer tous les clients
        clients = FrontClient.objects.all()
        
        total_created = 0
        
        for commercial in commerciaux:
            if commercial.role == 'responsable':
                continue  # Ignorer les responsables
                
            self.stdout.write(f"Traitement du commercial: {commercial.commercial} (ID: {commercial.id})")
            
            # Récupérer les clients assignés à ce commercial
            clients_commercial = clients.filter(commercial=commercial.commercial)
            
            for client in clients_commercial:
                # Vérifier si l'objectif existe déjà
                existing_objective = ClientVisitStats.objects.filter(
                    client=client,
                    commercial=commercial,
                    annee=current_year
                ).first()
                
                if existing_objective:
                    continue  # Objectif déjà existant
                
                # Déterminer l'objectif selon le classement
                if client.classement_client == 'A':
                    objectif = 10
                elif client.classement_client == 'B':
                    objectif = 5
                elif client.classement_client == 'C':
                    objectif = 1
                else:
                    objectif = 1  # Par défaut pour les clients sans classement
                
                # Créer l'objectif
                ClientVisitStats.objects.create(
                    client=client,
                    commercial=commercial,
                    annee=current_year,
                    objectif=objectif,
                    visites_valides=0
                )
                
                total_created += 1
                self.stdout.write(f"  - Client {client.id}: {client.rs_nom} -> Objectif {objectif}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ {total_created} objectifs créés pour {current_year}'
            )
        )
