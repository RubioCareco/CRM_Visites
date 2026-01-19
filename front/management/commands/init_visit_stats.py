from django.core.management.base import BaseCommand
from django.db import connection
from front.models import ClientVisitStats, Rendezvous, FrontClient, Commercial
from datetime import datetime

class Command(BaseCommand):
    help = 'Initialise les statistiques de visites pour tous les clients et commerciaux'

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee',
            type=int,
            default=datetime.now().year,
            help='Année pour laquelle initialiser les stats (défaut: année courante)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la réinitialisation des stats existantes'
        )

    def handle(self, *args, **options):
        annee = options['annee']
        force = options['force']
        
        self.stdout.write(f"Initialisation des statistiques de visites pour l'année {annee}...")
        
        if force:
            # Supprimer les stats existantes pour cette année
            ClientVisitStats.objects.filter(annee=annee).delete()
            self.stdout.write("Statistiques existantes supprimées.")
        
        # Récupérer tous les clients avec leur classement
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, classement_client 
                FROM front_client 
                WHERE classement_client IS NOT NULL 
                AND classement_client != ''
            """)
            clients_data = cursor.fetchall()
        
        stats_created = 0
        stats_updated = 0
        
        for client_id, classement in clients_data:
            try:
                client = FrontClient.objects.get(id=client_id)
                
                # Déterminer l'objectif basé sur le classement
                if classement.upper() == 'A':
                    objectif = 10
                elif classement.upper() == 'B':
                    objectif = 5
                elif classement.upper() == 'C':
                    objectif = 1
                else:
                    objectif = 1
                
                # Récupérer le commercial assigné au client
                commercial = client.commercial_id
                if not commercial:
                    continue
                
                # Récupérer l'objet Commercial
                try:
                    commercial_obj = Commercial.objects.get(id=commercial)
                except Commercial.DoesNotExist:
                    continue
                
                # Compter les visites validées pour cette année
                visites_valides = Rendezvous.objects.filter(
                    client=client,
                    commercial=commercial,
                    date_rdv__year=annee,
                    statut_rdv='valide'
                ).count()
                
                # Créer ou mettre à jour les stats
                stats, created = ClientVisitStats.objects.get_or_create(
                    client=client,
                    commercial=commercial_obj,
                    annee=annee,
                    defaults={
                        'objectif': objectif,
                        'visites_valides': visites_valides
                    }
                )
                
                if created:
                    stats_created += 1
                else:
                    # Mettre à jour si nécessaire
                    if stats.objectif != objectif or stats.visites_valides != visites_valides:
                        stats.objectif = objectif
                        stats.visites_valides = visites_valides
                        stats.save()
                        stats_updated += 1
                
            except FrontClient.DoesNotExist:
                self.stdout.write(f"Client {client_id} non trouvé, ignoré.")
            except Exception as e:
                self.stdout.write(f"Erreur pour le client {client_id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Initialisation terminée ! "
                f"Stats créées: {stats_created}, "
                f"Stats mises à jour: {stats_updated}"
            )
        ) 