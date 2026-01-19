from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import Rendezvous, ClientVisitStats, FrontClient
from datetime import datetime
import os
import threading
import logging
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

# Dictionnaire pour stocker les anciennes valeurs avant sauvegarde
_PRE_UPDATE_SNAPSHOT = {}

@receiver(pre_save, sender=FrontClient)
def snapshot_client_before_update(sender, instance, **kwargs):
    """Capture l'état avant sauvegarde pour comparer ensuite."""
    if instance.id:
        try:
            old = FrontClient.objects.get(id=instance.id)
            _PRE_UPDATE_SNAPSHOT[instance.id] = {
                'nom': old.nom,
                'prenom': old.prenom,
                'telephone': old.telephone,
                'email': old.email,
                'statut': old.statut,
                'code_comptable': old.code_comptable,
                'classement_client': old.classement_client,
                'rs_nom': old.rs_nom,
            }
        except FrontClient.DoesNotExist:
            _PRE_UPDATE_SNAPSHOT.pop(instance.id, None)

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

@receiver(post_save, sender=FrontClient)
def notify_responsable_on_client_modification(sender, instance, created, **kwargs):
    """Notifie le responsable commercial des modifications d'un client"""
    if created:  # Si c'est un nouveau client, pas besoin de notifier
        return
    
    # Récupérer l'utilisateur qui a fait la modification (depuis la session)
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.utils import timezone
    import pytz
    
    try:
        # Récupérer tous les responsables commerciaux
        responsables = User.objects.filter(
            groups__name='responsable'
        ).values_list('email', flat=True)
        
        if not responsables:
            print("⚠️ Aucun responsable trouvé pour l'envoi d'email")
            return
        
        # Convertir la date en fuseau horaire local (Europe/Paris)
        tz_local = pytz.timezone('Europe/Paris')
        date_modification = timezone.now().astimezone(tz_local)
        
        # Détecter les champs modifiés par comparaison avec le snapshot
        old = _PRE_UPDATE_SNAPSHOT.pop(instance.id, {}) if instance.id else {}
        fields_map = {
            'nom': 'Nom',
            'prenom': 'Prénom',
            'telephone': 'Téléphone',
            'email': 'Email',
            'statut': 'Statut',
            'code_comptable': 'Code comptable',
            'classement_client': 'Type de client',
            'rs_nom': 'Raison sociale',
        }
        modifications = {}
        for f, label in fields_map.items():
            old_val = old.get(f)
            new_val = getattr(instance, f, None)
            if (old != {}) and (old_val != new_val):
                modifications[label] = new_val or 'N/A'
        
        # Si aucune modification détectée, on n'envoie rien
        if not modifications:
            return

        # Préparer le contexte pour le template (logo via CID, donc pas d'URL)
        context = {
            'client': instance,
            'modifications': modifications,
            'date_modification': date_modification,
        }
        
        # Rendre le template HTML
        html_message = render_to_string('front/email_client_modification.html', context)
        
        # Préparer le sujet de l'email
        subject = f"Modification client : {instance.rs_nom or instance.nom or 'Client sans nom'}"
        
        # Préparer le chemin du logo pour pièce jointe inline
        from django.core.mail import EmailMultiAlternatives
        from email.mime.image import MIMEImage
        from pathlib import Path
        # Sélectionner le logo rubio2 avec fallback si extension différente
        img_dir = Path(settings.BASE_DIR) / 'front' / 'static' / 'front' / 'img'
        candidates = [
            'Rubio2-removeBG-preview.png',
            'Rubio2-removeBG-preview.webp',
            'Rubio2-removeBG-preview.jpg',
            'rubio2.png',
            'rubio2.webp',
            'rubio2.jpg',
            'Logo.png'
        ]
        logo_path = None
        logo_filename = 'Rubio2-removeBG-preview.png'
        for name in candidates:
            p = img_dir / name
            if p.exists():
                logo_path = p
                logo_filename = name
                break
        
        # Envoyer l'email HTML à tous les responsables avec image inline
        for email_responsable in responsables:
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body='\n',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email_responsable],
                )
                msg.attach_alternative(html_message, "text/html")
                # Attacher le logo inline si présent
                if logo_path.exists():
                    with open(logo_path, 'rb') as f:
                        logo_data = f.read()
                    image = MIMEImage(logo_data)
                    image.add_header('Content-ID', '<rubio-logo>')
                    image.add_header('Content-Disposition', 'inline', filename=logo_filename)
                    msg.attach(image)
                msg.send(fail_silently=False)
                print(f"✅ Email HTML envoyé au responsable : {email_responsable}")
            except Exception as e:
                print(f"❌ Erreur envoi email à {email_responsable}: {e}")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email de notification : {e}") 


# ==========================
# Déclenchement auto J+28 au login (1x/jour)
# ==========================

def _run_planning_job_background(dry_run: bool = False):
    try:
        from .services import ensure_visits_next_4_weeks
        stats = ensure_visits_next_4_weeks(dry_run=dry_run)
        logger.info("Planification J+28 exécutée: %s", stats)
        print(f"✅ Planification J+28 exécutée: {stats}")
    except Exception as e:
        logger.exception("Erreur planification J+28: %s", e)
        print(f"❌ Erreur planification J+28: {e}")


@receiver(user_logged_in)
def trigger_planning_on_login(sender, user, request, **kwargs):
    from django.conf import settings

    if not getattr(settings, 'GENERATION_AUTO_ENABLED', True):
        return

    cache_key = "planning:last_run"  # plus de date dans la clé
    last_run = cache.get(cache_key)
    now = dj_timezone.now()
    delta_days = (now - last_run).days if last_run else None

    # si jamais exécuté ET moins de 28 jours, on ignore
    if last_run and delta_days is not None and delta_days < 28:
        return

    # pose un verrou/horodatage pour 29 jours (sécurité)
    cache.set(cache_key, now, timeout=29 * 24 * 3600)

    dry_run = getattr(settings, 'GENERATION_AUTO_DRY_RUN', False)
    threading.Thread(
        target=_run_planning_job_background,
        kwargs={'dry_run': dry_run},
        daemon=True
    ).start()
