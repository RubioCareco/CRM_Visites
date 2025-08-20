from django.core.management.base import BaseCommand
from front.models import SatisfactionB2B
from front.utils import calculate_comprehensive_satisfaction_score


class Command(BaseCommand):
    help = 'Corrige les scores de satisfaction existants en base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait corrigé sans modifier la base',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("=== Correction des scores de satisfaction ===\n")
        
        if dry_run:
            self.stdout.write("Mode DRY-RUN - Aucune modification ne sera effectuée\n")
        
        # Récupérer toutes les satisfactions
        satisfactions = SatisfactionB2B.objects.all()
        
        if not satisfactions.exists():
            self.stdout.write("Aucune satisfaction trouvée en base de données.")
            return
        
        self.stdout.write(f"Nombre total de satisfactions: {satisfactions.count()}\n")
        
        corrected_count = 0
        error_count = 0
        
        for satisfaction in satisfactions:
            try:
                # Calculer le nouveau score hybride
                new_score = calculate_comprehensive_satisfaction_score(satisfaction)
                
                # Vérifier si le score actuel est incorrect (dépasse 10)
                current_score = satisfaction.score_hybride
                
                if current_score and current_score > 10:
                    self.stdout.write(f"  Satisfaction #{satisfaction.id} - {satisfaction.rs_nom}:")
                    self.stdout.write(f"    Score actuel: {current_score} (incorrect, dépasse 10)")
                    self.stdout.write(f"    Nouveau score: {new_score}")
                    
                    if not dry_run:
                        satisfaction.score_hybride = new_score
                        satisfaction.save()
                        self.stdout.write(f"    ✅ Corrigé")
                    else:
                        self.stdout.write(f"    🔍 Sera corrigé")
                    
                    corrected_count += 1
                    self.stdout.write("")
                
            except Exception as e:
                self.stdout.write(f"  ❌ Erreur lors du traitement de la satisfaction #{satisfaction.id}: {e}")
                error_count += 1
        
        # Résumé
        self.stdout.write("=== Résumé ===\n")
        if dry_run:
            self.stdout.write(f"Nombre de satisfactions qui seraient corrigées: {corrected_count}")
        else:
            self.stdout.write(f"Nombre de satisfactions corrigées: {corrected_count}")
        
        if error_count > 0:
            self.stdout.write(f"Nombre d'erreurs: {error_count}")
        
        if corrected_count == 0:
            self.stdout.write("✅ Aucune correction nécessaire - tous les scores sont corrects")
        else:
            if dry_run:
                self.stdout.write("🔍 Exécutez la commande sans --dry-run pour appliquer les corrections")
            else:
                self.stdout.write("✅ Toutes les corrections ont été appliquées")
        
        self.stdout.write("\n=== Fin de la correction ===") 