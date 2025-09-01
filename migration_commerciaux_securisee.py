#!/usr/bin/env python3
"""
Script de migration sécurisé pour corriger les noms de commerciaux
ATTENTION : Ce script ne modifie RIEN sans validation explicite !
"""

import os
import sys
import django
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_visites.settings')
django.setup()

from front.models import Commercial, FrontClient
from django.db import transaction

def analyser_situation():
    """Analyse la situation actuelle sans rien modifier"""
    print("🔍 ANALYSE DE LA SITUATION ACTUELLE")
    print("=" * 50)
    
    # État actuel des commerciaux
    print("\n📊 COMMERCIAUX DANS LA TABLE Commercial :")
    commerciaux = Commercial.objects.all()
    for c in commerciaux:
        print(f"  - ID {c.id}: '{c.commercial}'")
    
    # État actuel des clients
    print("\n👥 CLIENTS PAR NOM DE COMMERCIAL :")
    from django.db.models import Count
    repartition = FrontClient.objects.values('commercial').annotate(total=Count('id')).order_by('commercial')
    for rep in repartition:
        nom = rep['commercial'] if rep['commercial'] else '(VIDE)'
        print(f"  - '{nom}' : {rep['total']} clients")
    
    # Clients sans commercial
    clients_sans_commercial = FrontClient.objects.filter(commercial__isnull=True).count()
    if clients_sans_commercial > 0:
        print(f"\n⚠️  CLIENTS SANS COMMERCIAL : {clients_sans_commercial}")
    
    return commerciaux, repartition

def proposer_corrections(commerciaux, repartition):
    """Propose les corrections à apporter"""
    print("\n🔧 CORRECTIONS PROPOSÉES")
    print("=" * 50)
    
    corrections = []
    
    # Mapping des corrections
    mapping = {
        'COMMERCIAL1': 'Commercial 1',
        'COMMERCIAL2 -': 'Commercial 2',
        'COMMERCIAL2 et BORDEAUX EST': 'Commercial 2',
        '33-BORDEAUX': 'Commercial 3'
    }
    
    print("📝 MAPPING DES NOMS :")
    for ancien, nouveau in mapping.items():
        print(f"  '{ancien}' → '{nouveau}'")
    
    # Vérifier les commerciaux cibles
    noms_commerciaux = [c.commercial for c in commerciaux]
    print(f"\n✅ COMMERCIAUX CIBLES DISPONIBLES : {noms_commerciaux}")
    
    # Analyser l'impact
    print("\n📊 IMPACT DES CORRECTIONS :")
    for rep in repartition:
        ancien_nom = rep['commercial']
        if ancien_nom in mapping:
            nouveau_nom = mapping[ancien_nom]
            print(f"  '{ancien_nom}' ({rep['total']} clients) → '{nouveau_nom}'")
            corrections.append({
                'ancien': ancien_nom,
                'nouveau': nouveau_nom,
                'clients': rep['total']
            })
    
    return corrections

def simuler_migration(corrections):
    """Simule la migration sans rien modifier"""
    print("\n🧪 SIMULATION DE LA MIGRATION")
    print("=" * 50)
    
    total_clients_affectes = 0
    
    for correction in corrections:
        ancien = correction['ancien']
        nouveau = correction['nouveau']
        nb_clients = correction['clients']
        
        print(f"\n📋 Correction : '{ancien}' → '{nouveau}'")
        print(f"   Clients affectés : {nb_clients}")
        
        # Vérifier que le commercial cible existe
        commercial_cible = Commercial.objects.filter(commercial=nouveau).first()
        if commercial_cible:
            print(f"   ✅ Commercial cible trouvé : ID {commercial_cible.id}")
        else:
            print(f"   ❌ ERREUR : Commercial '{nouveau}' non trouvé !")
            return False
        
        total_clients_affectes += nb_clients
    
    print(f"\n📊 TOTAL CLIENTS AFFECTÉS : {total_clients_affectes}")
    return True

def executer_migration(corrections):
    """Exécute la migration avec validation"""
    print("\n🚀 EXÉCUTION DE LA MIGRATION")
    print("=" * 50)
    
    # Demander confirmation
    print("⚠️  ATTENTION : Cette opération va modifier la base de données !")
    print("📊 Résumé des modifications :")
    for correction in corrections:
        print(f"  - {correction['clients']} clients : '{correction['ancien']}' → '{correction['nouveau']}'")
    
    confirmation = input("\n❓ Confirmez-vous l'exécution ? (oui/non) : ").lower().strip()
    
    if confirmation != 'oui':
        print("❌ Migration annulée par l'utilisateur")
        return False
    
    # Exécuter la migration
    try:
        with transaction.atomic():
            print("\n🔄 Début de la migration...")
            
            for correction in corrections:
                ancien = correction['ancien']
                nouveau = correction['nouveau']
                nb_clients = correction['clients']
                
                print(f"  🔄 Mise à jour : '{ancien}' → '{nouveau}' ({nb_clients} clients)")
                
                # Mettre à jour les clients
                clients_mis_a_jour = FrontClient.objects.filter(commercial=ancien).update(commercial=nouveau)
                
                if clients_mis_a_jour == nb_clients:
                    print(f"    ✅ {clients_mis_a_jour} clients mis à jour")
                else:
                    print(f"    ⚠️  {clients_mis_a_jour} clients mis à jour (attendu: {nb_clients})")
            
            print("\n✅ Migration terminée avec succès !")
            return True
            
    except Exception as e:
        print(f"\n❌ ERREUR lors de la migration : {e}")
        print("🔄 Rollback automatique effectué")
        return False

def verifier_migration():
    """Vérifie que la migration s'est bien passée"""
    print("\n🔍 VÉRIFICATION POST-MIGRATION")
    print("=" * 50)
    
    # Vérifier la nouvelle répartition
    from django.db.models import Count
    nouvelle_repartition = FrontClient.objects.values('commercial').annotate(total=Count('id')).order_by('commercial')
    
    print("📊 NOUVELLE RÉPARTITION :")
    for rep in nouvelle_repartition:
        nom = rep['commercial'] if rep['commercial'] else '(VIDE)'
        print(f"  - '{nom}' : {rep['total']} clients")
    
    # Vérifier qu'il n'y a plus de noms incorrects
    noms_incorrects = ['COMMERCIAL1', 'COMMERCIAL2 -', 'COMMERCIAL2 et BORDEAUX EST', '33-BORDEAUX']
    for nom_incorrect in noms_incorrects:
        nb_clients = FrontClient.objects.filter(commercial=nom_incorrect).count()
        if nb_clients > 0:
            print(f"  ⚠️  '{nom_incorrect}' : {nb_clients} clients (NON CORRIGÉ)")
        else:
            print(f"  ✅ '{nom_incorrect}' : 0 clients (CORRIGÉ)")

def main():
    """Fonction principale"""
    print("🔒 SCRIPT DE MIGRATION SÉCURISÉ")
    print("=" * 50)
    print("Ce script corrige les noms de commerciaux sans rien casser")
    print("Aucune modification n'est effectuée sans votre validation !")
    print("=" * 50)
    
    # Étape 1 : Analyser
    commerciaux, repartition = analyser_situation()
    
    # Étape 2 : Proposer les corrections
    corrections = proposer_corrections(commerciaux, repartition)
    
    if not corrections:
        print("\n✅ Aucune correction nécessaire !")
        return
    
    # Étape 3 : Simuler
    if not simuler_migration(corrections):
        print("\n❌ La simulation a échoué. Migration annulée.")
        return
    
    # Étape 4 : Demander confirmation
    print("\n" + "=" * 50)
    print("📋 RÉSUMÉ DE LA MIGRATION")
    print("=" * 50)
    print("Ce script va :")
    for correction in corrections:
        print(f"  - Changer '{correction['ancien']}' en '{correction['nouveau']}' ({correction['clients']} clients)")
    
    print("\n⚠️  ATTENTION : Cette opération est IRRÉVERSIBLE !")
    print("💾 Assurez-vous d'avoir une sauvegarde de votre base de données.")
    
    # Étape 5 : Exécuter ou annuler
    choix = input("\n❓ Voulez-vous continuer ? (oui/non) : ").lower().strip()
    
    if choix == 'oui':
        if executer_migration(corrections):
            verifier_migration()
        else:
            print("\n❌ Migration échouée")
    else:
        print("\n❌ Migration annulée par l'utilisateur")

if __name__ == "__main__":
    main()
