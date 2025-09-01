#!/usr/bin/env python3
"""
Script de test pour la génération de RDV
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_visites.settings')
django.setup()

from front.utils import generer_rendezvous_simples
from front.models import FrontClient, Commercial, Rendezvous
from datetime import date

def test_generation():
    print("🔍 TEST DE LA GÉNÉRATION DE RDV")
    print("=" * 50)
    
    # Test 1 : Vérifier les clients
    print("\n📊 CLIENTS PAR COMMERCIAL :")
    commerciaux = Commercial.objects.filter(role='commercial')
    for c in commerciaux:
        clients = FrontClient.objects.filter(commercial=c.commercial)
        print(f"  - {c.commercial}: {clients.count()} clients")
    
    # Test 2 : Vérifier les RDV existants
    print(f"\n📅 RDV EXISTANTS AUJOURD'HUI ({date.today()}):")
    for c in commerciaux:
        rdvs = Rendezvous.objects.filter(commercial=c, date_rdv=date.today())
        print(f"  - {c.commercial}: {rdvs.count()} RDV")
    
    # Test 3 : Tester la génération
    print(f"\n🚀 TEST DE LA GÉNÉRATION :")
    try:
        rdv_crees = 0
        for commercial in Commercial.objects.filter(role='commercial'):
            rdv_crees += generer_rendezvous_simples(date.today(), commercial)
        print(f"  RDV générés: {rdv_crees}")
    except Exception as e:
        print(f"  ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 4 : Vérification finale
    print(f"\n✅ VÉRIFICATION FINALE :")
    for c in commerciaux:
        rdvs = Rendezvous.objects.filter(commercial=c, date_rdv=date.today())
        print(f"  - {c.commercial}: {rdvs.count()} RDV")
        if rdvs.count() > 0:
            for rdv in rdvs[:3]:
                print(f"    * {rdv.heure_rdv} - {rdv.client.rs_nom}")

if __name__ == "__main__":
    test_generation()
