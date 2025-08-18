from django.core.management.base import BaseCommand
from front.models import Adresse
import re

class Command(BaseCommand):
    help = "Corrige automatiquement les adresses problématiques"

    def handle(self, *args, **options):
        adresses = Adresse.objects.filter(latitude__isnull=True)
        corrected_count = 0
        
        for adresse in adresses:
            original_adresse = adresse.adresse
            original_ville = adresse.ville
            original_cp = adresse.code_postal
            
            # Corrections automatiques
            corrections_made = False
            
            # 1. Corriger les villes avec tirets manquants
            ville_corrections = {
                'VILLEFRANCHE SUR SAO': 'VILLEFRANCHE-SUR-SAÔNE',
                'BOURG EN BRESSE': 'BOURG-EN-BRESSE',
                'SAINT GERMAIN EN LAYE': 'SAINT-GERMAIN-EN-LAYE',
                'LA CHAPELLE SUR ERDR': 'LA CHAPELLE-SUR-ERDRE',
                'LA VALETTE DU VAR': 'LA VALETTE-DU-VAR',
                'SAINT PALAIS': 'SAINT-PALAIS',
                'BELLEVILLE-SUR-MEUSE': 'BELLEVILLE-SUR-MEUSE',  # Déjà correct
                'L ISLE ADAM': 'L\'ISLE-ADAM',
                'SAINT OUEN': 'SAINT-OUEN',
                'ST DIDIER SUR BEAUJE': 'SAINT-DIDIER-SUR-BEAUJEU',
                'SAINT JAMMES': 'SAINT-JEAN-PIED-DE-PORT',
            }
            
            if adresse.ville in ville_corrections:
                adresse.ville = ville_corrections[adresse.ville]
                corrections_made = True
                self.stdout.write(f"Ville corrigée: {original_ville} → {adresse.ville}")
            
            # 2. Nettoyer les adresses avec des noms d'entreprise
            if adresse.adresse:
                # Supprimer les notes entre parenthèses
                adresse.adresse = re.sub(r'\s*\([^)]*\)', '', adresse.adresse)
                
                # Supprimer les notes après tiret en fin de ligne
                adresse.adresse = re.sub(r'\s*-\s*[^-]*$', '', adresse.adresse)
                
                # Nettoyer les espaces multiples
                adresse.adresse = re.sub(r'\s+', ' ', adresse.adresse).strip()
                
                # Supprimer les adresses vides ou trop courtes
                if len(adresse.adresse) < 3:
                    adresse.adresse = None
                
                if adresse.adresse != original_adresse:
                    corrections_made = True
                    self.stdout.write(f"Adresse nettoyée: {original_adresse} → {adresse.adresse}")
            
            # 3. Corriger les codes postaux problématiques
            cp_corrections = {
                '1000': '01000',  # BOURG EN BRESSE
                '8130': '08130',  # ATTIGNY
            }
            
            if adresse.code_postal in cp_corrections:
                adresse.code_postal = cp_corrections[adresse.code_postal]
                corrections_made = True
                self.stdout.write(f"Code postal corrigé: {original_cp} → {adresse.code_postal}")
            
            # Sauvegarder si des corrections ont été faites
            if corrections_made:
                adresse.save()
                corrected_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Correction terminée: {corrected_count} adresses corrigées")
        ) 