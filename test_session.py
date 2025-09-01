#!/usr/bin/env python3
"""
Script simple pour tester la session utilisateur
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_visites.settings')
django.setup()

from front.models import Commercial, SatisfactionB2B

def test_session():
    print("🔍 TEST DE LA SESSION UTILISATEUR")
    print("=" * 50)
    
    # Test 1 : Vérifier la satisfaction
    satisfaction_uuid = '8feffd57-01cf-475a-9d75-24c9b1b419a3'
    satisfaction = SatisfactionB2B.objects.filter(uuid=satisfaction_uuid).first()
    
    if satisfaction:
        print(f"✅ Satisfaction trouvée : {satisfaction}")
        print(f"   RDV : {satisfaction.rdv}")
        print(f"   Commercial du RDV : {satisfaction.rdv.commercial}")
        print(f"   Commercial ID : {satisfaction.rdv.commercial.id}")
        print(f"   Commercial nom : {satisfaction.rdv.commercial.commercial}")
        print(f"   Commercial __str__ : {str(satisfaction.rdv.commercial)}")
    else:
        print("❌ Satisfaction non trouvée")
        return
    
    print("\n📊 COMMERCIAUX DISPONIBLES :")
    commerciaux = Commercial.objects.all()
    for c in commerciaux:
        print(f"  - ID {c.id}: '{c.commercial}' (prenom: '{c.prenom}', nom: '{c.nom}')")
    
    print("\n💡 POUR RÉSOUDRE L'ERREUR 403 :")
    print("   Vous devez être connecté avec :")
    print(f"   - commercial_id = {satisfaction.rdv.commercial.id}")
    print(f"   - OU role = 'responsable' ou 'admin'")
    
    print("\n🔑 VÉRIFIEZ VOTRE CONNEXION :")
    print("   1. Allez sur http://127.0.0.1:8000/login/")
    print("   2. Connectez-vous avec un compte qui a :")
    print(f"      - commercial_id = {satisfaction.rdv.commercial.id}")
    print("      - OU role = 'responsable' ou 'admin'")
    print("   3. Puis testez l'URL de téléchargement")

if __name__ == "__main__":
    test_session()
