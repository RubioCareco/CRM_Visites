from django.core.management.base import BaseCommand
from django.db import connection
from front.models import FrontClient, ClientVisitStats

class Command(BaseCommand):
    help = 'Met à jour tous les objectifs annuels des clients selon leur classement actuel'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Mise à jour des objectifs annuels...')
        
        updated_count = 0
        
        with connection.cursor() as cursor:
            # Récupérer tous les clients avec leur classement
            cursor.execute("""
                SELECT id, classement_client 
                FROM front_client 
                WHERE classement_client IS NOT NULL AND classement_client != ''
            """)
            
            clients = cursor.fetchall()
            
            for client_id, classement in clients:
                # Déterminer l'objectif selon le classement
                classement_upper = classement.upper()
                if 'A' in classement_upper:
                    objectif = 10
                elif 'B' in classement_upper:
                    objectif = 5
                elif 'C' in classement_upper:
                    objectif = 1
                else:
                    objectif = 1  # Cas par défaut
                
                # Mettre à jour tous les ClientVisitStats pour ce client
                cursor.execute("""
                    UPDATE front_clientvisitstats 
                    SET objectif = %s 
                    WHERE client_id = %s
                """, [objectif, client_id])
                
                if cursor.rowcount > 0:
                    updated_count += cursor.rowcount
                    self.stdout.write(f"✅ Client {client_id}: {classement} → {objectif} visites/an")
        
        self.stdout.write(
            self.style.SUCCESS(f'🎉 Mise à jour terminée ! {updated_count} objectifs mis à jour.')
        ) 