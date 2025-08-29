from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import Rendezvous, ClientVisitStats, FrontClient
from datetime import datetime

@receiver(post_save, sender=Rendezvous)
def update_visit_stats_on_rdv_change(sender, instance, created, **kwargs):
    """Met à jour les statistiques de visites quand un RDV change de statut"""
    if not instance.client or not instance.commercial:
        return
    
    # Déterminer l'objectif annuel basé sur le classement du client
    objectif = get_objectif_annuel_from_client(instance.client)
    
    # Mettre à jour les stats pour l'année du RDV
    annee = instance.date_rdv.year
    
    with transaction.atomic():
        stats, created = ClientVisitStats.objects.get_or_create(
            client=instance.client,
            commercial=instance.commercial,
            annee=annee,
            defaults={'objectif': objectif, 'visites_valides': 0}
        )
        
        # Si l'objectif a changé, le mettre à jour
        if stats.objectif != objectif:
            stats.objectif = objectif
            stats.save()
        
        # Recalculer le nombre total de visites validées pour cette année
        visites_valides = Rendezvous.objects.filter(
            client=instance.client,
            commercial=instance.commercial,
            date_rdv__year=annee,
            statut_rdv='valide'
        ).count()
        
        # Mettre à jour seulement si le nombre a changé
        if stats.visites_valides != visites_valides:
            stats.visites_valides = visites_valides
            stats.save()

@receiver(post_delete, sender=Rendezvous)
def update_visit_stats_on_rdv_delete(sender, instance, **kwargs):
    """Met à jour les statistiques quand un RDV est supprimé"""
    if not instance.client or not instance.commercial:
        return
    
    annee = instance.date_rdv.year
    
    try:
        with transaction.atomic():
            stats = ClientVisitStats.objects.get(
                client=instance.client,
                commercial=instance.commercial,
                annee=annee
            )
            
            # Recalculer le nombre total de visites validées
            visites_valides = Rendezvous.objects.filter(
                client=instance.client,
                commercial=instance.commercial,
                date_rdv__year=annee,
                statut_rdv='valide'
            ).count()
            
            stats.visites_valides = visites_valides
            stats.save()
    except ClientVisitStats.DoesNotExist:
        pass

def get_objectif_annuel_from_client(client):
    """Récupère l'objectif annuel basé sur le classement du client"""
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT classement_client 
            FROM front_client 
            WHERE id = %s
        """, [client.id])
        
        result = cursor.fetchone()
        if result and result[0]:
            classement = result[0].upper()
            if classement == 'A':
                return 10
            elif classement == 'B':
                return 5
            elif classement == 'C':
                return 1
        
        return 1  # Objectif par défaut

@receiver(post_save, sender=FrontClient)
def update_visit_stats_on_client_classement_change(sender, instance, created, **kwargs):
    """Met à jour les objectifs annuels quand le classement d'un client change"""
    if created:  # Si c'est un nouveau client, pas besoin de mettre à jour
        return
    
    # Déterminer le nouvel objectif basé sur le classement actuel
    if instance.classement_client:
        classement = instance.classement_client.upper()
        if 'A' in classement:
            nouvel_objectif = 10
        elif 'B' in classement:
            nouvel_objectif = 5
        elif 'C' in classement:
            nouvel_objectif = 1
        else:
            nouvel_objectif = 1  # Cas par défaut
    else:
        nouvel_objectif = 1  # N/A = 1 visite par an
    
    # Mettre à jour tous les ClientVisitStats existants pour ce client
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE front_clientvisitstats 
            SET objectif = %s 
            WHERE client_id = %s
        """, [nouvel_objectif, instance.id])
        
        print(f"✅ Objectif mis à jour pour le client {instance.id}: {instance.classement_client} → {nouvel_objectif} visites/an") 