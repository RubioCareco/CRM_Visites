#!/usr/bin/env python3
"""
Script de diagnostic pour le client LABATAILLE et ses RDV multiples
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_visites.settings')
django.setup()

from front.models import FrontClient, Rendezvous, Commercial
from django.utils import timezone
from datetime import date, timedelta

def debug_labataille():
    print("🔍 DIAGNOSTIC DU CLIENT LABATAILLE")
    print("=" * 60)
    
    # Rechercher le client LABATAILLE
    client = FrontClient.objects.filter(rs_nom__icontains='LABATAILLE').first()
    if not client:
        print("❌ Client LABATAILLE non trouvé")
        return
    
    print(f"👤 Client trouvé : {client.rs_nom}")
    print(f"   ID : {client.id}")
    print(f"   Commercial : {client.commercial}")
    print(f"   Classement : {getattr(client, 'classement_client', 'Non défini')}")
    
    # Récupérer tous les RDV de ce client
    rdvs = Rendezvous.objects.filter(client=client).order_by('date_rdv', 'heure_rdv')
    
    print(f"\n📊 ANALYSE DES RENDEZ-VOUS")
    print("-" * 60)
    print(f"   Total RDV : {rdvs.count()}")
    
    # Analyser par statut
    statuts = rdvs.values_list('statut_rdv', flat=True).distinct()
    print(f"   Statuts distincts : {list(statuts)}")
    
    for statut in statuts:
        count = rdvs.filter(statut_rdv=statut).count()
        print(f"   - {statut} : {count} RDV")
    
    # Analyser par date (derniers 30 jours)
    aujourd_hui = date.today()
    il_y_a_30_jours = aujourd_hui - timedelta(days=30)
    
    rdvs_recents = rdvs.filter(date_rdv__gte=il_y_a_30_jours)
    print(f"\n📅 RDV des 30 derniers jours : {rdvs_recents.count()}")
    
    # Analyser la fréquence par date
    dates_rdv = rdvs_recents.values_list('date_rdv', flat=True).distinct().order_by('date_rdv')
    
    print(f"\n📅 Fréquence des RDV par date :")
    print("-" * 60)
    
    for date_rdv in dates_rdv:
        rdvs_ce_jour = rdvs_recents.filter(date_rdv=date_rdv)
        statuts_ce_jour = rdvs_ce_jour.values_list('statut_rdv', flat=True)
        print(f"   {date_rdv} : {rdvs_ce_jour.count()} RDV - {list(statuts_ce_jour)}")
    
    # Vérifier s'il y a des doublons
    print(f"\n🔍 VÉRIFICATION DES DOUBLONS")
    print("-" * 60)
    
    # Compter les RDV par date
    from django.db.models import Count
    doublons = rdvs_recents.values('date_rdv').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('date_rdv')
    
    if doublons.exists():
        print("   ⚠️  DOUBLONS DÉTECTÉS !")
        for doublon in doublons:
            date_rdv = doublon['date_rdv']
            count = doublon['count']
            print(f"      - {date_rdv} : {count} RDV")
            
            # Afficher les détails des RDV dupliqués
            rdvs_dupliques = rdvs_recents.filter(date_rdv=date_rdv)
            for rdv in rdvs_dupliques:
                print(f"        * ID {rdv.id} - {rdv.statut_rdv} - {rdv.heure_rdv} - {rdv.objet}")
    else:
        print("   ✅ Aucun doublon détecté")
    
    # Vérifier la logique de génération automatique
    print(f"\n🚨 ANALYSE DE LA GÉNÉRATION AUTOMATIQUE")
    print("-" * 60)
    
    # Vérifier s'il y a des RDV générés automatiquement
    rdvs_auto = rdvs.filter(objet__icontains='automatique')
    if rdvs_auto.exists():
        print(f"   ⚠️  RDV automatiques détectés : {rdvs_auto.count()}")
        for rdv in rdvs_auto[:5]:  # Afficher les 5 premiers
            print(f"      - {rdv.date_rdv} : {rdv.objet}")
    else:
        print("   ✅ Aucun RDV automatique détecté")
    
    # Vérifier les RDV avec objet vide
    rdvs_vides = rdvs.filter(objet__isnull=True) | rdvs.filter(objet='')
    if rdvs_vides.exists():
        print(f"   ⚠️  RDV avec objet vide : {rdvs_vides.count()}")
    
    print(f"\n🎯 RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 60)
    print("✅ Problème identifié : RDV multiples pour le même client")
    print("🔍 Causes possibles :")
    print("   - Génération automatique en boucle")
    print("   - Script de génération exécuté plusieurs fois")
    print("   - Bug dans la logique de création de RDV")
    print("   - Import de données corrompues")
    print("💡 Solutions à vérifier :")
    print("   - Vérifier les scripts de génération automatique")
    print("   - Nettoyer les RDV dupliqués")
    print("   - Corriger la logique de génération")

if __name__ == '__main__':
    debug_labataille()
