from django.core.management.base import BaseCommand
from front.models import Rendezvous, ClientVisitStats, FrontClient, Commercial
from datetime import date, time
from django.utils import timezone

class Command(BaseCommand):
    help = 'Teste le fonctionnement des signaux en créant un RDV de test'

    def handle(self, *args, **options):
        self.stdout.write("Test des signaux de mise à jour des statistiques...")
        
        # Récupérer un client et un commercial
        try:
            client = FrontClient.objects.first()
            commercial = Commercial.objects.first()
            
            if not client or not commercial:
                self.stdout.write("Erreur: Client ou commercial non trouvé")
                return
            
            self.stdout.write(f"Client: {client.rs_nom}")
            self.stdout.write(f"Commercial: {commercial.nom}")
            
            # Vérifier les stats avant
            stats_avant = ClientVisitStats.objects.filter(
                client=client,
                commercial=commercial,
                annee=date.today().year
            ).first()
            
            if stats_avant:
                self.stdout.write(f"Stats avant: {stats_avant.visites_valides}/{stats_avant.objectif}")
            else:
                self.stdout.write("Aucune stat avant")
            
            # Créer un RDV de test
            rdv = Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=date.today(),
                heure_rdv=time(14, 0),
                objet="Test signal",
                statut_rdv='valide'
            )
            
            self.stdout.write(f"RDV créé avec ID: {rdv.id}")
            
            # Vérifier les stats après
            stats_apres = ClientVisitStats.objects.filter(
                client=client,
                commercial=commercial,
                annee=date.today().year
            ).first()
            
            if stats_apres:
                self.stdout.write(f"Stats après: {stats_apres.visites_valides}/{stats_apres.objectif}")
            else:
                self.stdout.write("Aucune stat après")
            
            # Nettoyer le RDV de test
            rdv.delete()
            self.stdout.write("RDV de test supprimé")
            
            # Vérifier les stats finales
            stats_final = ClientVisitStats.objects.filter(
                client=client,
                commercial=commercial,
                annee=date.today().year
            ).first()
            
            if stats_final:
                self.stdout.write(f"Stats finales: {stats_final.visites_valides}/{stats_final.objectif}")
            else:
                self.stdout.write("Aucune stat finale")
                
        except Exception as e:
            self.stdout.write(f"Erreur: {e}") 