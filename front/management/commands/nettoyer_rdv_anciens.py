from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from front.models import Rendezvous, Commercial, ActivityLog


class Command(BaseCommand):
    help = 'Nettoie automatiquement les RDV anciens non traités pour tous les commerciaux'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans effectuer les modifications',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Nombre de jours en arrière pour nettoyer (défaut: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_back = options['days']
        
        # Date de référence (hier par défaut)
        reference_date = date.today() - timedelta(days=days_back)
        
        self.stdout.write(
            self.style.SUCCESS(f'🔍 Nettoyage des RDV du {reference_date} (il y a {days_back} jour(s))')
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  MODE DRY-RUN - Aucune modification ne sera effectuée'))
        
        # Récupérer tous les commerciaux
        commerciaux = Commercial.objects.all()
        
        total_rdv_traites = 0
        total_rdv_annules = 0
        
        for commercial in commerciaux:
            self.stdout.write(f'\n👤 Commercial: {commercial.prenom} {commercial.nom}')
            
            # RDV à venir du jour de référence
            rdvs_anciens = Rendezvous.objects.filter(
                commercial=commercial,
                statut_rdv='a_venir',
                date_rdv=reference_date
            )
            
            if not rdvs_anciens.exists():
                self.stdout.write('  ✅ Aucun RDV ancien à traiter')
                continue
            
            self.stdout.write(f'  📅 {rdvs_anciens.count()} RDV à traiter du {reference_date}')
            
            # Logique de nettoyage
            for rdv in rdvs_anciens:
                client_nom = rdv.client.rs_nom if rdv.client else "Client supprimé"
                
                if dry_run:
                    self.stdout.write(f'    🔍 RDV {rdv.heure_rdv} - {client_nom} → Serait marqué comme "en_retard"')
                else:
                    # Marquer comme "en_retard" pour que le commercial puisse le traiter
                    rdv.statut_rdv = 'en_retard'
                    rdv.save()
                    
                    # Log de l'action
                    ActivityLog.objects.create(
                        commercial=commercial,
                        action_type='RDV_AUTO_RETARD',
                        description=f"RDV du {reference_date} {rdv.heure_rdv} - {client_nom} automatiquement marqué comme en retard"
                    )
                    
                    self.stdout.write(f'    ⚠️  RDV {rdv.heure_rdv} - {client_nom} → Marqué comme "en_retard"')
                    total_rdv_traites += 1
        
        # Résumé final
        self.stdout.write('\n' + '='*50)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'📊 RÉSUMÉ DRY-RUN - {total_rdv_traites} RDV seraient traités')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✅ NETTOYAGE TERMINÉ - {total_rdv_traites} RDV traités')
            )
            
            # Vérification post-nettoyage
            self.stdout.write('\n🔍 Vérification post-nettoyage:')
            for commercial in commerciaux:
                rdvs_en_retard = Rendezvous.objects.filter(
                    commercial=commercial,
                    statut_rdv='en_retard',
                    date_rdv=reference_date
                ).count()
                
                if rdvs_en_retard > 0:
                    self.stdout.write(f'  👤 {commercial.prenom} {commercial.nom}: {rdvs_en_retard} RDV en retard')
        
        self.stdout.write('\n💡 Prochaines étapes:')
        self.stdout.write('  1. Les commerciaux doivent valider ou annuler les RDV marqués "en_retard"')
        self.stdout.write('  2. Exécuter cette commande quotidiennement (cron job)')
        self.stdout.write('  3. Ou l\'intégrer dans le dashboard pour exécution automatique') 