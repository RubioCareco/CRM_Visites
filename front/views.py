from django.shortcuts import render, redirect, get_object_or_404
from .models import Commercial, Rendezvous, CommentaireRdv, ImportClientCorrected, SatisfactionB2B, FrontClient, ActivityLog
from django.contrib.auth.hashers import check_password, make_password
from functools import wraps
from django.http import JsonResponse, HttpResponse, Http404
from datetime import datetime, timedelta, date
from django.utils import timezone
import json
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import models
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
import base64
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_GET
import pandas as pd
from django.db.models import Avg, Count, Q
from django.db.models.functions import Coalesce, TruncDay, TruncWeek, TruncMonth, TruncYear
from .models import Adresse
from front.utils import generer_rendezvous_automatiques
from django.db import connection

def nettoyer_rdv_anciens_automatiquement():
    """
    Nettoie automatiquement les RDV anciens non traités pour tous les commerciaux.
    Cette fonction est appelée automatiquement depuis le dashboard.
    """
    from datetime import date, timedelta
    
    # Date de référence (hier par défaut)
    reference_date = date.today() - timedelta(days=1)
    
    # Récupérer tous les commerciaux
    commerciaux = Commercial.objects.all()
    
    total_rdv_traites = 0
    
    for commercial in commerciaux:
        # RDV à venir du jour de référence
        rdvs_anciens = Rendezvous.objects.filter(
            commercial=commercial,
            statut_rdv='a_venir',
            date_rdv=reference_date
        )
        
        if rdvs_anciens.exists():
            # Marquer comme "en_retard" pour que le commercial puisse le traiter
            for rdv in rdvs_anciens:
                rdv.statut_rdv = 'en_retard'
                rdv.save()
                
                # Log de l'action
                ActivityLog.objects.create(
                    commercial=commercial,
                    action_type='RDV_AUTO_RETARD',
                    description=f"RDV du {reference_date} {rdv.heure_rdv} - {rdv.client.rs_nom if rdv.client else 'Client supprimé'} automatiquement marqué comme en retard"
                )
                
                total_rdv_traites += 1
    
    return total_rdv_traites

# 🔐 Décorateur de protection
def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'commercial_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

# 🔐 Vue de connexion
def login_view(request):
    erreur = False
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        commercial = Commercial.objects.filter(email=email).first()

        if commercial and check_password(password, commercial.password):
            request.session['commercial_id'] = commercial.id
            request.session['commercial_nom'] = commercial.commercial
            request.session['role'] = commercial.role
            if commercial.role in ['responsable', 'admin']:
                return redirect('dashboard_responsable')
            else:
                return redirect('dashboard')
        else:
            erreur = True
    return render(request, 'front/login.html', {'erreur': erreur})

# 🔐 Déconnexion
def logout_view(request):
    request.session.flush()
    return redirect('login')

reset_tokens = {}

def reset_password(request):
    print("RESET PASSWORD VIEW CALLED")
    if request.method == 'POST':
        email = request.POST.get('email')
        users = User.objects.filter(email=email)
        commercials = Commercial.objects.filter(email=email)
        if not users.exists() and not commercials.exists():
            return render(request, 'front/reset_password.html', {'error': "Aucun compte avec cet email."})
        reset_links = []
        for user in users:
            token = get_random_string(48)
            reset_tokens[token] = ('user', user.id)
            reset_link = request.build_absolute_uri(reverse('new_password')) + f'?token={token}'
            subject = render_to_string('front/reset_password_subject.txt').strip()
            html_content = render_to_string('front/reset_password_email.html', {
                'reset_link': reset_link,
                'user': user,
            })
            text_content = f"Pour réinitialiser votre mot de passe, cliquez sur ce lien : {reset_link}"
            print("HTML CONTENT:", html_content)
            msg = EmailMultiAlternatives(subject, text_content, 'bznjamin.gillens@gmail.com', [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            reset_links.append(reset_link)
        for commercial in commercials:
            token = get_random_string(48)
            reset_tokens[token] = ('commercial', commercial.id)
            reset_link = request.build_absolute_uri(reverse('new_password')) + f'?token={token}'
            subject = render_to_string('front/reset_password_subject.txt').strip()
            html_content = render_to_string('front/reset_password_email.html', {
                'reset_link': reset_link,
                'user': commercial,
            })
            text_content = f"Pour réinitialiser votre mot de passe, cliquez sur ce lien : {reset_link}"
            print("HTML CONTENT:", html_content)
            msg = EmailMultiAlternatives(subject, text_content, 'bznjamin.gillens@gmail.com', [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            reset_links.append(reset_link)
        return render(request, 'front/reset_password_done.html', {'email': email, 'reset_link': reset_links[-1]})
    return render(request, 'front/reset_password.html')

def new_password(request):
    token = request.GET.get('token')
    token_info = reset_tokens.get(token)
    if not token_info:
        return render(request, 'front/new_password.html', {'error': "Lien invalide ou expiré."})
    user_type, obj_id = token_info
    if request.method == 'POST':
        pwd = request.POST.get('password')
        if user_type == 'user':
            user = User.objects.get(id=obj_id)
            user.set_password(pwd)
            user.save()
        elif user_type == 'commercial':
            commercial = Commercial.objects.get(id=obj_id)
            commercial.password = make_password(pwd)
            commercial.save()
        del reset_tokens[token]
        return redirect('login')
    return render(request, 'front/new_password.html', {'token': token})

# 🏠 Dashboard
@login_required
def dashboard(request):
    # --- Génération automatique des RDV à la demande (hors week-end) ---
    today = date.today()
    if today.weekday() < 5:  # 0=lundi, ..., 4=vendredi
        from front.models import Rendezvous
        deja_genere = Rendezvous.objects.filter(date_rdv=today, statut_rdv='a_venir').exists()
        if not deja_genere:
            generer_rendezvous_automatiques(today)
    # --- Fin génération automatique ---
    
    # --- Nettoyage automatique des RDV anciens ---
    rdvs_nettoyes = nettoyer_rdv_anciens_automatiquement()
    if rdvs_nettoyes > 0:
        # Stocker l'info pour l'afficher dans le template
        request.session['rdvs_nettoyes'] = rdvs_nettoyes
    # --- Fin nettoyage automatique ---
    commercial_id = request.session.get('commercial_id')
    commercial = Commercial.objects.get(id=commercial_id)
    now = timezone.now()

    def enrichir_compteurs_annuels(rdv: Rendezvous) -> None:
        """Ajoute rdv.obj_annuel, rdv.rdv_realises_annuel et rdv.rdv_ratio (texte X/Y) en utilisant les stats pré-calculées."""
        if not rdv.client:
            rdv.obj_annuel = 1
            rdv.rdv_realises_annuel = 0
            rdv.rdv_ratio = "0/1"
            return
        
        # Utiliser les statistiques pré-calculées si disponibles
        try:
            from .models import ClientVisitStats
            annee = timezone.now().year
            stats = ClientVisitStats.objects.filter(
                client=rdv.client,
                commercial=rdv.commercial,
                annee=annee
            ).first()
            
            if stats:
                rdv.obj_annuel = stats.objectif
                rdv.rdv_realises_annuel = stats.visites_valides
                rdv.rdv_ratio = f"{stats.visites_valides}/{stats.objectif}"
            else:
                # Fallback si pas de stats (calcul à la volée)
                from django.db import connection
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT classement_client FROM front_client WHERE id = %s", [rdv.client.id])
                        row = cursor.fetchone()
                        lettre = (row[0] if row else None)
                        if not lettre:
                            obj = 1
                        else:
                            lettre = str(lettre).strip().upper()
                            if lettre == 'A':
                                obj = 10
                            elif lettre == 'B':
                                obj = 5
                            elif lettre == 'C':
                                obj = 1
                            else:
                                obj = 1
                        
                        tries = Rendezvous.objects.filter(
                            client=rdv.client,
                            commercial=rdv.commercial,
                            statut_rdv='valide',
                            date_rdv__year=annee,
                        ).count()
                        
                        rdv.obj_annuel = obj
                        rdv.rdv_realises_annuel = tries
                        rdv.rdv_ratio = f"{tries}/{obj}"
                except Exception:
                    rdv.obj_annuel = 1
                    rdv.rdv_realises_annuel = 0
                    rdv.rdv_ratio = "0/1"
        except ImportError:
            # Si le modèle n'existe pas encore, utiliser le calcul à la volée
            from django.db import connection
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT classement_client FROM front_client WHERE id = %s", [rdv.client.id])
                    row = cursor.fetchone()
                    lettre = (row[0] if row else None)
                    if not lettre:
                        obj = 1
                    else:
                        lettre = str(lettre).strip().upper()
                        if lettre == 'A':
                            obj = 10
                        elif lettre == 'B':
                            obj = 5
                        elif lettre == 'C':
                            obj = 1
                        else:
                            obj = 1
                    
                    annee = timezone.now().year
                    tries = Rendezvous.objects.filter(
                        client=rdv.client,
                        commercial=rdv.commercial,
                        statut_rdv='valide',
                        date_rdv__year=annee,
                    ).count()
                    
                    rdv.obj_annuel = obj
                    rdv.rdv_realises_annuel = tries
                    rdv.rdv_ratio = f"{tries}/{obj}"
            except Exception:
                rdv.obj_annuel = 1
                rdv.rdv_realises_annuel = 0
                rdv.rdv_ratio = "0/1"

    visites_recentes = []
    a_venir = []
    a_rappeler = []

    rdvs = Rendezvous.objects.filter(commercial=commercial).order_by('-date_rdv', '-heure_rdv')

    for rdv in rdvs:
        if rdv.statut_rdv == 'valide':
            visites_recentes.append(rdv)
        elif rdv.statut_rdv == 'annule':
            a_rappeler.append(rdv)
        elif rdv.statut_rdv == 'a_venir':
            a_venir.append(rdv)

    # Ajout du compteur de rendez-vous validés par client
    for rdv in visites_recentes:
        last_rdv = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide',
            date_rdv__lt=rdv.date_rdv
        ).order_by('-date_rdv', '-heure_rdv').first()
        rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
        
        # Compteur de rendez-vous validés pour ce client
        rdv.nb_rdv_valides = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide'
        ).count()
        # Compteurs annuels (ne s'affichent pas ici mais prêts si besoin)
        enrichir_compteurs_annuels(rdv)
        
    for rdv in a_rappeler:
        last_rdv = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide',
            date_rdv__lt=rdv.date_rdv
        ).order_by('-date_rdv', '-heure_rdv').first()
        rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
        
        # Compteur de rendez-vous validés pour ce client
        rdv.nb_rdv_valides = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide'
        ).count()
        # Compteurs annuels (ne s'affichent pas ici mais prêts si besoin)
        enrichir_compteurs_annuels(rdv)

    # Préparation des données client de manière robuste
    def prepare_client_data(rdv):
        try:
            client, adresse, client_type = get_client_and_adresse(rdv.client.id)
            # Attacher les données client et adresse au rdv pour le template
            rdv.client_data = client
            rdv.adresse_data = adresse
            rdv.client_type = client_type
        except Exception as e:
            # Fallback si get_client_and_adresse échoue
            rdv.client_data = rdv.client
            rdv.adresse_data = {
                "adresse": getattr(rdv.client, 'adresse', ''),
                "code_postal": getattr(rdv.client, 'code_postal', ''),
                "ville": getattr(rdv.client, 'ville', ''),
            }
            rdv.client_type = "fallback"

        # S'assurer que tous les champs nécessaires sont présents
        if not hasattr(rdv.client_data, 'email') or not rdv.client_data.email:
            rdv.client_data.email = getattr(rdv.client_data, 'e_mail', '')
        if not hasattr(rdv.client_data, 'civilite'):
            rdv.client_data.civilite = getattr(rdv.client_data, 'civilite', '')
        if not hasattr(rdv.client_data, 'statut'):
            rdv.client_data.statut = getattr(rdv.client_data, 'statut', '')
        if not hasattr(rdv.client_data, 'code_comptable'):
            rdv.client_data.code_comptable = getattr(rdv.client_data, 'code_comptable', '')
        if not hasattr(rdv.client_data, 'telephone'):
            rdv.client_data.telephone = getattr(rdv.client_data, 'telephone', '')
        if not hasattr(rdv.client_data, 'rs_nom'):
            rdv.client_data.rs_nom = getattr(rdv.client_data, 'rs_nom', '')
        if not hasattr(rdv.client_data, 'nom'):
            rdv.client_data.nom = getattr(rdv.client_data, 'nom', '')
        if not hasattr(rdv.client_data, 'prenom'):
            rdv.client_data.prenom = getattr(rdv.client_data, 'prenom', '')

    for rdv in visites_recentes:
        prepare_client_data(rdv)
        rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first() if rdv.client else None
    for rdv in a_venir:
        prepare_client_data(rdv)
        rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first() if rdv.client else None
        # Ajout de l'attribut en_retard
        if rdv.date_rdv and rdv.heure_rdv:
            dt = datetime.combine(rdv.date_rdv, rdv.heure_rdv)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            rdv.en_retard = dt < timezone.now()
        else:
            rdv.en_retard = False
        # Ajout du compteur de rendez-vous validés pour ce client (comme les autres colonnes)
        rdv.nb_rdv_valides = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide'
        ).count()
        # Objectif et ratio annuel (à afficher côté UI pour les "à venir")
        enrichir_compteurs_annuels(rdv)
    for rdv in a_rappeler:
        prepare_client_data(rdv)
        rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first() if rdv.client else None

    # === NOUVEAU : Pagination des RDV à venir par jour ===
    # Récupérer la date demandée (par défaut aujourd'hui)
    date_demandee = request.GET.get('date', today.isoformat())
    try:
        date_demandee = date.fromisoformat(date_demandee)
    except ValueError:
        date_demandee = today

    # Récupérer les RDV à venir pour la date demandée (max 7)
    rdvs_jour = Rendezvous.objects.filter(
        commercial=commercial,
        date_rdv=date_demandee,
        statut_rdv='a_venir'
    ).order_by('heure_rdv')[:7]

    # Préparer les données pour ces RDV
    for rdv in rdvs_jour:
        prepare_client_data(rdv)
        rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first() if rdv.client else None
        if rdv.date_rdv and rdv.heure_rdv:
            dt = datetime.combine(rdv.date_rdv, rdv.heure_rdv)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            rdv.en_retard = dt < timezone.now()
        else:
            rdv.en_retard = False
        rdv.nb_rdv_valides = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv='valide'
        ).count()
        # Objectif et ratio annuel (à afficher côté UI pour les "à venir")
        enrichir_compteurs_annuels(rdv)

    # Calculer les dates de navigation (précédent/suivant)
    date_precedente = date_demandee - timedelta(days=1)
    date_suivante = date_demandee + timedelta(days=1)
    
    # Vérifier s'il y a des RDV sur ces dates
    has_rdv_precedent = Rendezvous.objects.filter(
        commercial=commercial,
        date_rdv=date_precedente,
        statut_rdv='a_venir'
    ).exists()
    
    has_rdv_suivant = Rendezvous.objects.filter(
        commercial=commercial,
        date_rdv=date_suivante,
        statut_rdv='a_venir'
    ).exists()

    return render(request, 'front/dashboard.html', {
        'commercial': commercial,
        'visites_recentes': visites_recentes,
        'rdvs_a_venir': a_venir,  # Garder pour compatibilité
        'rdvs_jour': rdvs_jour,    # Nouveau : RDV du jour sélectionné
        'a_rappeler': a_rappeler,
        'date_courante': date_demandee,
        'date_precedente': date_precedente,
        'date_suivante': date_suivante,
        'has_rdv_precedent': has_rdv_precedent,
        'has_rdv_suivant': has_rdv_suivant,
    })

# ➕ Nouveau client
@login_required
def new_client(request):
    commercial_id = request.session.get('commercial_id')
    commercial = Commercial.objects.get(id=commercial_id)

    if request.method == 'POST':
        if 'add_rdv' in request.POST:
            request.session['client_temp'] = {
                'nom': request.POST.get('nom'),
                'prenom': request.POST.get('prenom'),
                'entreprise': request.POST.get('entreprise'),
                'siret': request.POST.get('siret'),
                'adresse': request.POST.get('adresse'),
                'code_postal': request.POST.get('code_postal'),
                'ville': request.POST.get('ville'),
                'email': request.POST.get('email'),
                'telephone': request.POST.get('telephone')
            }
            request.session['show_success'] = True
            return redirect('/add-rdv?from=new-client')

        temp_data = request.session.get('client_temp') or {}
        nom = request.POST.get('nom') or temp_data.get('nom')
        prenom = request.POST.get('prenom') or temp_data.get('prenom')
        entreprise = request.POST.get('entreprise') or temp_data.get('entreprise')
        siret = request.POST.get('siret') or temp_data.get('siret')
        adresse = request.POST.get('adresse') or temp_data.get('adresse')
        code_postal = request.POST.get('code_postal') or temp_data.get('code_postal')
        ville = request.POST.get('ville') or temp_data.get('ville')
        email = request.POST.get('email') or temp_data.get('email')
        telephone = request.POST.get('telephone') or temp_data.get('telephone')

        client = FrontClient.objects.create(
            nom=nom,
            prenom=prenom,
            rs_nom=entreprise,
            siret=siret,
            email=email,
            telephone=telephone,
            commercial=commercial
        )

        # Ajout : création de l'adresse liée
        Adresse.objects.create(
            client=client,
            adresse=adresse,
            code_postal=code_postal,
            ville=ville
        )

        # Création d'un rendez-vous si besoin (après ajout manuel)
        rdv_temp = request.session.get('rdv_temp')
        if rdv_temp:
            Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=rdv_temp['date_rdv'],
                heure_rdv=rdv_temp['heure_rdv'],
                objet=rdv_temp.get('objet'),
                notes=rdv_temp.get('notes')
            )

        # Nettoyage des données temporaires
        request.session.pop('client_temp', None)
        request.session.pop('rdv_temp', None)

        # Affichage notification succès puis redirection JS
        return render(request, 'front/new_client.html', {
            'client_temp': None,
            'rdv_temp': None,
            'success': True
        })

    # En GET, on récupère le flag de succès éventuel
    success = request.GET.get('success') == '1'
    client_temp = request.session.get('client_temp')
    rdv_temp = request.session.get('rdv_temp')
    return render(request, 'front/new_client.html', {
        'client_temp': client_temp,
        'rdv_temp': rdv_temp,
        'success': success
    })

# ➕ Nouveau rendez-vous
@login_required
def add_rdv(request):
    commercial_id = request.session.get('commercial_id')
    commercial = Commercial.objects.get(id=commercial_id)
    from_new_client = request.GET.get('from') == 'new-client'

    # Pré-remplissage client si client_id passé en GET
    client_id_prefill = request.GET.get('client_id')
    client_prefill = None
    if client_id_prefill:
        try:
            client_prefill, adresse_prefill, client_type_prefill = get_client_and_adresse(client_id_prefill)
        except ImportClientCorrected.DoesNotExist:
            client_prefill = None

    role = request.session.get('role')
    commerciaux_list = None
    if role in ['responsable', 'admin']:
        commerciaux_list = Commercial.objects.filter(role='commercial')

    error_message = None
    if request.method == 'POST':
        try:
            if 'is_temp_rdv' in request.POST:
                request.session['rdv_temp'] = {
                    'date_rdv': request.POST.get('date_rdv'),
                    'heure_rdv': request.POST.get('heure_rdv'),
                    'objet': request.POST.get('objet'),
                    'notes': request.POST.get('notes')
                }
                return redirect('new_client')

            # Si responsable/admin, on prend le commercial choisi, sinon celui de la session
            if role in ['responsable', 'admin']:
                commercial_id_selected = request.POST.get('commercial_id')
                commercial = Commercial.objects.get(id=commercial_id_selected)
            else:
                commercial_id = request.session.get('commercial_id')
                commercial = Commercial.objects.get(id=commercial_id)

            client_id = request.POST.get('client_id')
            client, adresse, client_type = get_client_and_adresse(client_id)

            Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=request.POST.get('date_rdv'),
                heure_rdv=request.POST.get('heure_rdv'),
                objet=request.POST.get('objet'),
                notes=request.POST.get('notes'),
                statut_rdv='a_venir',  # Par défaut, à venir
                rs_nom=client.rs_nom  # Ajouter le rs_nom du client
            )

            # Enregistrer l'activité dans le journal
            ActivityLog.objects.create(
                commercial=commercial,
                action_type='RDV_AJOUTE',
                description=f'Nouveau RDV ajouté pour {client.rs_nom}'
            )

            # Ajout : si show_success dans la session, on revient sur new_client avec notification
            if request.session.get('show_success'):
                request.session.pop('show_success')
                return redirect('/new-client?success=1')

            if role in ['responsable', 'admin']:
                return redirect('dashboard_responsable')
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard')

        except ImportClientCorrected.DoesNotExist:
            error_message = "Le client sélectionné est introuvable."
        except Exception as e:
            error_message = f"Une erreur est survenue : {e}"

    # Si responsable/admin, on affiche tous les clients, sinon seulement ceux du commercial
    if role in ['responsable', 'admin']:
        clients = ImportClientCorrected.objects.all()
    else:
        nom_normalise = commercial.commercial.replace(' ', '').upper()
        clients = ImportClientCorrected.objects.extra(
            where=["REPLACE(UPPER(commercial), ' ', '') = %s"], params=[nom_normalise]
        )
    client_temp = request.session.get('client_temp') if from_new_client else None
    next_url = request.GET.get('next', '/dashboard')

    return render(request, 'front/add_rdv.html', {
        'clients': clients,
        'client_temp': client_temp,
        'next': next_url,
        'from_new_client': from_new_client,
        'client_prefill': client_prefill,
        'role': role,
        'commerciaux_list': commerciaux_list,
        'error_message': error_message,
        'today_date': date.today().isoformat(),
    })

# 📁 Fiche client
@login_required
def customer_file(request):
    return render(request, 'front/customer_file.html')

# 👤 Profil commercial
@login_required
def profils_commerciaux(request):
    # Assurez-vous que seul un responsable ou admin peut voir cette page
    role = request.session.get('role')
    if role not in ['responsable', 'admin']:
        return redirect('dashboard') # Rediriger si pas les droits

    commerciaux = Commercial.objects.filter(role='commercial')
    return render(request, 'front/profils_commerciaux.html', {'commerciaux': commerciaux})

@login_required
def profil(request, commercial_id=None):
	# Si un ID est fourni, on affiche le profil de ce commercial.
	# Sinon, on affiche le profil de l'utilisateur connecté.
	if commercial_id:
		# Un responsable peut voir le profil d'un commercial
		role = request.session.get('role')
		if role in ['responsable', 'admin']:
			commercial = get_object_or_404(Commercial, id=commercial_id)
		else:
			# Un commercial ne peut voir que son propre profil
			return redirect('profil')
	else:
		# Pas d'ID, on prend celui de la session
		session_commercial_id = request.session.get('commercial_id')
		commercial = get_object_or_404(Commercial, id=session_commercial_id)

	if request.method == 'POST':
		# La logique de mise à jour reste la même
		commercial.nom = request.POST.get('nom') or commercial.nom
		commercial.prenom = request.POST.get('prenom') or commercial.prenom
		commercial.email = request.POST.get('email') or commercial.email
		commercial.telephone = request.POST.get('telephone') or commercial.telephone
		# Gestion du switch absent
		was_absent = commercial.is_absent
		is_absent_now = bool(request.POST.get('is_absent'))
		commercial.is_absent = is_absent_now
		commercial.save()

		# Geler/dégeler les rendez-vous à venir si changement d'état
		from .models import Rendezvous, ActivityLog
		today = timezone.now().date()
		if not was_absent and is_absent_now:
			# Passage à absent : geler tous les RDV à venir
			Rendezvous.objects.filter(
				commercial=commercial,
				statut_rdv='a_venir',
				date_rdv__gte=today
			).update(statut_rdv='gele')
			# Log activité absence
			ActivityLog.objects.create(
				commercial=commercial,
				action_type='ABSENCE_ON',
				description=f"{commercial.prenom} {commercial.nom} s'est déclaré absent"
			)
		elif was_absent and not is_absent_now:
			# Passage à présent :
			# 1) Dégeler les RDV gelés à venir
			Rendezvous.objects.filter(
				commercial=commercial,
				statut_rdv='gele',
				date_rdv__gte=today
			).update(statut_rdv='a_venir')
			# 2) Reporter à aujourd'hui les RDV gelés d'hier (non honorés)
			from datetime import datetime, timedelta, time as time_cls
			yesterday = today - timedelta(days=1)
			geles_hier = Rendezvous.objects.filter(
				commercial=commercial,
				statut_rdv='gele',
				date_rdv=yesterday
			).order_by('heure_rdv')
			if geles_hier.exists():
				# Créneaux déjà occupés aujourd'hui pour ce commercial
				occupied_times = set(
					Rendezvous.objects.filter(
						commercial=commercial,
						date_rdv=today
					).values_list('heure_rdv', flat=True)
				)
				for rdv in geles_hier:
					start_time = rdv.heure_rdv or time_cls(8, 0)
					current_dt = datetime.combine(today, start_time)
					# Décaler par pas de 35 minutes si le créneau est déjà pris
					while current_dt.time() in occupied_times:
						current_dt += timedelta(minutes=35)
					rdv.date_rdv = today
					rdv.heure_rdv = current_dt.time()
					rdv.statut_rdv = 'a_venir'
					rdv.save()
					occupied_times.add(rdv.heure_rdv)
			# Log activité retour
			ActivityLog.objects.create(
				commercial=commercial,
				action_type='ABSENCE_OFF',
				description=f"{commercial.prenom} {commercial.nom} est de retour (présent)"
			)

		# Redirection appropriée
		if 'commercial_id' in request.resolver_match.kwargs:
			# Si on éditait un commercial spécifique, on retourne à la liste
			return redirect('profils_commerciaux')
		else:
			# Sinon, on retourne à son propre dashboard
			role = request.session.get('role')
			if role in ['responsable', 'admin']:
				return redirect('dashboard_responsable')
			else:
				return redirect('dashboard')

	# On passe une variable pour savoir si on peut éditer (le user peut éditer son profil, ou un responsable peut éditer un commercial)
	can_edit = (not commercial_id) or (request.session.get('role') in ['responsable', 'admin'])
	is_profil_commercial = commercial_id is not None

	return render(request, 'front/profil.html', {
		'commercial': commercial,
		'role': request.session.get('role'),
		'can_edit': can_edit,
		'is_profil_commercial': is_profil_commercial,
	})

# ❌ Supprimer le rdv temporaire
@login_required
def delete_temp_rdv(request):
	request.session.pop('rdv_temp', None)
	return JsonResponse({'status': 'ok'})

# ✅ Mise à jour du statut via modal dynamique
@login_required
def update_statut(request, uuid, statut):
	print("DEBUG méthode reçue :", request.method)
	rdv = get_object_or_404(Rendezvous, uuid=uuid)
	if not (request.user.is_superuser or (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id'))):
		raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")

	if request.method == 'POST':
		data = json.loads(request.body)
		commentaire = data.get('commentaire', '')

		if statut == "valider":
			rdv.statut_rdv = 'valide'
			rdv.date_statut = timezone.now()
			if commentaire.strip():
				rdv.notes = commentaire  # (optionnel)
				client, adresse, client_type = get_client_and_adresse(rdv.client.id)
				rs_nom = adresse["adresse"] if adresse else getattr(rdv.client, 'rs_nom', None) or getattr(rdv.client, 'nom', None) or ''
				commercial_id = request.session.get('commercial_id')
				commercial = Commercial.objects.get(id=commercial_id) if commercial_id else None
				CommentaireRdv.objects.create(
					rdv=rdv,
					auteur=request.user if request.user.is_authenticated else None,
					commercial=commercial,
					texte=commentaire,
					rs_nom=rs_nom
				)
		elif statut == "annuler":
			rdv.statut_rdv = 'annule'
			rdv.date_statut = timezone.now()
			if commentaire.strip():
				rdv.notes = commentaire  # (optionnel)
				client, adresse, client_type = get_client_and_adresse(rdv.client.id)
				rs_nom = adresse["adresse"] if adresse else getattr(rdv.client, 'rs_nom', None) or getattr(rdv.client, 'nom', None) or ''
				commercial_id = request.session.get('commercial_id')
				commercial = Commercial.objects.get(id=commercial_id) if commercial_id else None
				CommentaireRdv.objects.create(
					rdv=rdv,
					auteur=request.user if request.user.is_authenticated else None,
					commercial=commercial,
					texte=commentaire,
					rs_nom=rs_nom
				)
		elif statut == "commentaire":
			# On ajoute juste un commentaire sans changer le statut
			if commentaire.strip():
				client, adresse, client_type = get_client_and_adresse(rdv.client.id)
				rs_nom = adresse["adresse"] if adresse else getattr(rdv.client, 'rs_nom', None) or getattr(rdv.client, 'nom', None) or ''
				commercial_id = request.session.get('commercial_id')
				commercial = Commercial.objects.get(id=commercial_id) if commercial_id else None
				CommentaireRdv.objects.create(
					rdv=rdv,
					auteur=request.user if request.user.is_authenticated else None,
					commercial=commercial,
					texte=commentaire,
					rs_nom=rs_nom
				)
			return JsonResponse({'status': 'ok'})

		rdv.save()

		# Enregistrer l'activité dans le journal
		action_type = ''
		if statut in ['valide', 'valider']:
			action_type = 'RDV_VALIDE'
			description = f"RDV avec {rdv.client.rs_nom} validé"
		elif statut in ['annule', 'annuler']:
			action_type = 'RDV_ANNULE'
			description = f"RDV avec {rdv.client.rs_nom} annulé"
		
		if action_type:
			ActivityLog.objects.create(
				commercial=rdv.commercial,
				action_type=action_type,
				description=description
			)

		client = rdv.client
		
		# Calculer le nombre de RDV validés pour ce client
		nb_rdv_valides = Rendezvous.objects.filter(
			client__rs_nom=client.rs_nom,
			statut_rdv='valide'
		).count()
		
		# On récupère tous les champs utiles pour la carte
		return JsonResponse({
			'status': 'ok',
			'id': rdv.id,
			'nom': getattr(client, 'prénom', ''),
			'prenom': getattr(client, 'prénom', ''),
			'rs_nom': getattr(client, 'rs_nom', ''),
			'civilite': getattr(client, 'civilite', ''),
			'adresse': getattr(client, 'adresse', ''),
			'code_postal': getattr(client, 'code_postal', ''),
			'ville': getattr(client, 'ville', ''),
			'telephone': getattr(client, 'telephone', ''),
			'e_mail': getattr(client, 'e_mail', ''),
			'code_comptable': getattr(client, 'code_comptable', ''),
			'statut': rdv.statut_rdv,
			'date': rdv.date_rdv.strftime('%d/%m/%Y'),
			'heure': rdv.heure_rdv.strftime('%H:%M'),
			'date_statut': rdv.date_statut.strftime('%d/%m/%Y %H:%M') if rdv.date_statut else '',
			'nb_rdv_valides': nb_rdv_valides,
		})
	else:
		print("DEBUG : Méthode non autorisée pour update_statut")
		return JsonResponse({'status': 'error', 'message': f"Méthode {request.method} non autorisée"}, status=405)

from django.http import JsonResponse

@login_required
def get_rdv_info(request, uuid):
	try:
		rdv = Rendezvous.objects.get(uuid=uuid)
		if not (request.user.is_superuser or (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id'))):
			raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
		client, adresse, client_type = get_client_and_adresse(rdv.client.id)
		# Récupérer les commentaires liés à ce rendez-vous
		commentaires = rdv.commentaires.order_by('date_creation').all()
		commentaires_data = [
			{
				'auteur': c.auteur.username if c.auteur else 'Système',
				'texte': c.texte,
				'date': c.date_creation.strftime('%d/%m/%Y %H:%M')
			}
			for c in commentaires
		]
		# Si aucun commentaire structuré, mais qu'il y a des notes, on l'affiche comme commentaire initial
		if not commentaires_data and rdv.notes:
			commentaires_data.append({
				'auteur': 'Système',
				'texte': rdv.notes,
				'date': rdv.date_creation.strftime('%d/%m/%Y %H:%M')
			})
		return JsonResponse({
			'entreprise': adresse["adresse"] if adresse else getattr(rdv.client, 'rs_nom', ''),
			'nom': getattr(client, 'prénom', ''),
			'prenom': getattr(client, 'prénom', ''),
			'adresse': adresse["adresse"] if adresse else getattr(client, 'adresse', ''),
			'code_postal': adresse["code_postal"] if adresse else getattr(client, 'code_postal', ''),
			'ville': adresse["ville"] if adresse else getattr(client, 'ville', ''),
			'telephone': getattr(client, 'telephone', ''),
			'email': getattr(client, 'e_mail', ''),
			'statut': getattr(client, 'statut', ''),
			'code_comptable': getattr(client, 'code_comptable', ''),
			'date': rdv.date_rdv.strftime('%d/%m/%Y'),
			'heure': rdv.heure_rdv.strftime('%H:%M'),
			'commentaires': commentaires_data
		})
	except Rendezvous.DoesNotExist:
		return JsonResponse({'error': 'Rendez-vous introuvable'}, status=404)
	
def client_file(request):
	per_page = int(request.GET.get('per_page', 50))
	page_number = request.GET.get('page', 1)
	role = request.session.get('role')

	commerciaux = None
	if role in ['responsable', 'admin']:
		commerciaux = Commercial.objects.filter(role='commercial')

	# Optimisation : Utiliser prefetch_related pour les adresses
	clients_qs = FrontClient.objects.prefetch_related('adresses')
	selected_commercial = request.GET.get('commercial')

	# Filtres personnalisés - Appliquer directement sur les querysets
	if selected_commercial and role in ['responsable', 'admin']:
		# Normalisation du filtre pour les responsables/admins
		selected_commercial_normalise = selected_commercial.replace(' ', '').upper()
		clients_qs = clients_qs.extra(
			where=["REPLACE(UPPER(commercial), ' ', '') = %s"], params=[selected_commercial_normalise]
		)
	elif role not in ['responsable', 'admin']:
		commercial_nom = request.session.get('commercial_nom')
		if commercial_nom:
			nom_normalise = commercial_nom.replace(' ', '').upper()
			clients_qs = clients_qs.extra(
				where=["REPLACE(UPPER(commercial), ' ', '') = %s"], params=[nom_normalise]
			)

	filter_raison = request.GET.get('filterRaison')
	if filter_raison:
		clients_qs = clients_qs.filter(rs_nom__icontains=filter_raison)

	# Construire les couples de manière optimisée
	couples = []
	for client in clients_qs:
		adresses = list(client.adresses.all())
		
		# Appliquer les filtres d'adresse directement sur la liste
		if request.GET.get('filterAdresse'):
			adresses = [a for a in adresses if request.GET.get('filterAdresse').lower() in (a.adresse or '').lower()]
		if request.GET.get('filterCP'):
			adresses = [a for a in adresses if (a.code_postal or '').startswith(request.GET.get('filterCP'))]
		if request.GET.get('filterVille'):
			adresses = [a for a in adresses if request.GET.get('filterVille').lower() in (a.ville or '').lower()]
		
		# Ajouter les couples avec adresses filtrées
		for adresse in adresses:
			couples.append((client, adresse))
		
		# Si aucun filtre d'adresse et aucune adresse, ajouter le client sans adresse
		if not any([request.GET.get('filterAdresse'), request.GET.get('filterCP'), request.GET.get('filterVille')]) and not adresses:
			couples.append((client, None))

	from django.core.paginator import Paginator
	paginator = Paginator(couples, per_page)
	page_obj = paginator.get_page(page_number)

	return render(request, 'front/client_file.html', {
		'page_obj': page_obj,
		'clients_with_adresse': page_obj,
		'per_page': per_page,
		'paginator': paginator,
		'role': role,
		'commerciaux': commerciaux,
		'selected_commercial': selected_commercial,
	})	

@login_required
def historique_rdv(request):
	commercial_id = request.session.get('commercial_id')
	commercial = Commercial.objects.get(id=commercial_id)
	rdvs_archives = Rendezvous.objects.filter(commercial=commercial).order_by('-date_rdv', '-heure_rdv')
	visites_recentes = []
	a_rappeler = []
	historique_general = []
	for rdv in rdvs_archives:
		# Utilisation du champ statut_rdv
		if rdv.statut_rdv == 'valide':
			visites_recentes.append(rdv)
			historique_general.append(rdv)
		elif rdv.statut_rdv == 'annule':
			a_rappeler.append(rdv)
			historique_general.append(rdv)
		# Ajout de l'adresse principale du client
		if rdv.client:
			rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first()
		else:
			rdv.adresse_principale = None
	# On trie l'historique général par date décroissante (déjà fait par la requête)
	for rdv in visites_recentes:
		last_rdv = Rendezvous.objects.filter(
			client=rdv.client,
			commercial=rdv.commercial,
			statut_rdv__in=['valide', 'annule'],
			date_rdv__lt=rdv.date_rdv
		).order_by('-date_rdv', '-heure_rdv').first()
		rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
	for rdv in a_rappeler:
		last_rdv = Rendezvous.objects.filter(
			client=rdv.client,
			commercial=rdv.commercial,
			statut_rdv__in=['valide', 'annule'],
			date_rdv__lt=rdv.date_rdv
		).order_by('-date_rdv', '-heure_rdv').first()
		rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
	for rdv in historique_general:
		last_rdv = Rendezvous.objects.filter(
			client=rdv.client,
			commercial=rdv.commercial,
			statut_rdv__in=['valide', 'annule'],
			date_rdv__lt=rdv.date_rdv
		).order_by('-date_rdv', '-heure_rdv').first()
		rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
	# --- Détection filtre date actif pour badge ---
	date_label = None
	if 'date_debut' in request.GET and 'date_fin' in request.GET:
		if request.GET['date_debut'] == request.GET['date_fin']:
			date_label = f"Jour : {request.GET['date_debut']}"
		else:
			date_label = f"Période : {request.GET['date_debut']} au {request.GET['date_fin']}"
	elif 'mois' in request.GET:
		date_label = f"Mois : {request.GET['mois']}"
	elif 'annee' in request.GET:
		date_label = f"Année : {request.GET['annee']}"
	elif 'semaine' in request.GET:
		date_label = f"Semaine : {request.GET['semaine']}"
	return render(request, 'front/historique_rdv.html', {
		'commercial': commercial,
		'visites_recentes': visites_recentes,
		'a_rappeler': a_rappeler,
		'historique_general': historique_general,
		'role': request.session.get('role'),
		'date_label': date_label,
		'request': request,
	})	

@login_required
def historique_rdv_resp(request):
	# Filtrer selon le statut si besoin (ex: ?statut=valide)
	statut = request.GET.get('statut')
	date_debut = request.GET.get('date_debut')
	date_fin = request.GET.get('date_fin')
	
	rdvs_archives = Rendezvous.objects.all().order_by('-date_rdv', '-heure_rdv')
	
	# Logique de filtrage par date selon le statut
	if date_debut or date_fin:
		try:
			from datetime import date, timedelta
			
			# Préparer les dates de filtrage
			date_debut_obj = None
			date_fin_obj = None
			
			if date_debut:
				date_debut_obj = date.fromisoformat(date_debut)
			
			if date_fin:
				date_fin_obj = date.fromisoformat(date_fin) + timedelta(days=1)
			
			# Filtrer selon le statut et la date appropriée
			if statut == 'valide':
				# Pour les RDV validés, filtrer sur date_statut (date de validation)
				if date_debut_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='valide',
						date_statut__date__gte=date_debut_obj
					)
				if date_fin_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='valide',
						date_statut__date__lt=date_fin_obj
					)
				
			elif statut == 'annule':
				# Pour les RDV annulés, filtrer sur date_rdv (date prévue)
				if date_debut_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='annule',
						date_rdv__gte=date_debut_obj
					)
				if date_fin_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='annule',
						date_rdv__lt=date_fin_obj
					)
				
			elif statut == 'a_venir':
				# Pour les RDV à venir, filtrer sur date_rdv (date prévue)
				if date_debut_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='a_venir',
						date_rdv__gte=date_debut_obj
					)
				if date_fin_obj:
					rdvs_archives = rdvs_archives.filter(
						statut_rdv='a_venir',
						date_rdv__lt=date_fin_obj
					)
				
			else:
				# Pour 'all' ou pas de statut, filtrer sur les deux champs
				from django.db.models import Q
				date_filter = Q()
				
				if date_debut_obj:
					date_filter &= (
						Q(statut_rdv__in=['valide', 'annule'], date_statut__date__gte=date_debut_obj) |
						Q(statut_rdv='a_venir', date_rdv__gte=date_debut_obj)
					)
				
				if date_fin_obj:
					date_filter &= (
						Q(statut_rdv__in=['valide', 'annule'], date_statut__date__lt=date_fin_obj) |
						Q(statut_rdv='a_venir', date_rdv__lt=date_fin_obj)
					)
				
				rdvs_archives = rdvs_archives.filter(date_filter)
				
		except ValueError:
			# En cas d'erreur de conversion de date, on ignore le filtrage
			pass
	
	# DEBUG : Afficher toutes les dates de RDV annulés avant filtrage
	print('--- RDV annulés AVANT filtrage ---')
	for rdv in Rendezvous.objects.filter(statut_rdv='annule').order_by('date_rdv'):
		print(f"Annulé : {rdv.date_rdv} (date_statut={rdv.date_statut})")

	# Correction : si aucun filtre, on transmet tout
	if not statut and not date_debut and not date_fin:
		visites_recentes = [r for r in rdvs_archives if r.statut_rdv == 'valide']
		a_rappeler = [r for r in rdvs_archives if r.statut_rdv == 'annule']
		historique_general = [r for r in rdvs_archives if r.statut_rdv in ['valide', 'annule']]
	else:
		visites_recentes = []
		a_rappeler = []
		historique_general = []
		for rdv in rdvs_archives:
			if statut and statut != 'all' and rdv.statut_rdv != statut:
				continue
			if rdv.statut_rdv == 'valide':
				visites_recentes.append(rdv)
				historique_general.append(rdv)
			elif rdv.statut_rdv == 'annule':
				a_rappeler.append(rdv)
				historique_general.append(rdv)
			# Ajout de l'adresse principale du client
			if rdv.client:
				rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first()
			else:
				rdv.adresse_principale = None
	
	# DEBUG : Afficher toutes les dates de RDV annulés après filtrage
	print('--- RDV annulés APRES filtrage ---')
	for rdv in rdvs_archives.filter(statut_rdv='annule').order_by('date_rdv'):
		print(f"Annulé filtré : {rdv.date_rdv} (date_statut={rdv.date_statut})")

	# Ajout systématique de l'adresse principale pour chaque rdv (sécurisé)
	for rdv in set(visites_recentes + a_rappeler + historique_general):
		if not hasattr(rdv, 'adresse_principale') or rdv.adresse_principale is None:
			rdv.adresse_principale = Adresse.objects.filter(client=rdv.client).first() if getattr(rdv, 'client', None) else None

	# Tri spécifique selon l'onglet
	visites_recentes = sorted(visites_recentes, key=lambda r: (r.date_statut or r.date_rdv, r.heure_rdv), reverse=True)
	a_rappeler = sorted(a_rappeler, key=lambda r: (r.date_statut or r.date_rdv, r.heure_rdv), reverse=True)
	# Pour l'historique général :
	def tri_pertinent(r):
		if r.statut_rdv in ['valide', 'annule'] and r.date_statut:
			return (r.date_statut, r.heure_rdv)
		return (r.date_rdv, r.heure_rdv)
	historique_general = sorted(historique_general, key=tri_pertinent, reverse=True)

	# Créer le label pour le badge de filtre
	date_label = None
	if date_debut and date_fin:
		date_label = f"Du {date_debut} au {date_fin}"
	elif date_debut:
		date_label = f"À partir du {date_debut}"
	elif date_fin:
		date_label = f"Jusqu'au {date_fin}"
	
	# Créer le label pour le badge de statut
	statut_label = None
	if statut:
		if statut == 'valide':
			statut_label = "Validés"
		elif statut == 'annule':
			statut_label = "Annulés"
		elif statut == 'a_venir':
			statut_label = "À venir"
	
	# Calcul de la dernière visite validée antérieure pour affichage dans le template
	for rdv in set(visites_recentes + a_rappeler + historique_general):
		try:
			last_rdv = Rendezvous.objects.filter(
				client=rdv.client,
				commercial=rdv.commercial,
				statut_rdv='valide',
				date_rdv__lt=rdv.date_rdv
			).order_by('-date_rdv', '-heure_rdv').first()
			rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
		except Exception:
			rdv.derniere_visite = None

	return render(request, 'front/historique_rdv_resp.html', {
		'visites_recentes': visites_recentes,
		'a_rappeler': a_rappeler,
		'historique_general': historique_general,
		'role': request.session.get('role'),
		'date_label': date_label,
		'statut_label': statut_label,
	})

@csrf_exempt  # À remplacer par @login_required + gestion CSRF si besoin
def update_client(request, client_id):
	if request.method == "POST":
		try:
			data = json.loads(request.body)
			client, adresse, client_type = get_client_and_adresse(client_id)
			
			# Mettre à jour les champs du client
			client.telephone = data.get("telephone", client.telephone)
			client.email = data.get("email", client.email)
			client.classement_client = data.get("classement_client", client.classement_client)
			client.save()
			
			# Mettre à jour l'adresse si elle existe
			if adresse and client_type == "front":
				# Chercher l'adresse principale du client
				from .models import Adresse
				adresse_obj = Adresse.objects.filter(client=client).first()
				if adresse_obj:
					adresse_obj.adresse = data.get("adresse", adresse_obj.adresse)
					adresse_obj.code_postal = data.get("code_postal", adresse_obj.code_postal)
					adresse_obj.ville = data.get("ville", adresse_obj.ville)
					adresse_obj.save()
			
			return JsonResponse({"success": True})
		except Exception as e:
			return JsonResponse({"success": False, "error": str(e)})
	return JsonResponse({"success": False, "error": "Méthode non autorisée"})	

def satisfaction_b2b(request):
	note_recommandation_choices = list(range(1, 11))
	rs_nom = request.GET.get('rs_nom') or request.POST.get('rs_nom')
	# Récupérer l'ID du commercial depuis la session au lieu de l'URL
	commercial_id = request.session.get('commercial_id')
	rdv_uuid = request.GET.get('rdv_id') or request.POST.get('rdv_id')

	if request.method == 'POST':
		data = request.POST
		# On construit un objet 'reponse' pour le template PDF
		reponse = {
			'date_soumission': timezone.now(),
			'qualite_satisfait': data.get('qualite_satisfait'),
			'note_qualite_globale': data.get('note_qualite_globale'),
			'probleme_qualite': data.get('probleme_qualite'),
			'type_probleme': data.get('type_probleme'),
			'delai_satisfait': data.get('delai_satisfait'),
			'delai_moyen': data.get('delai_moyen'),
			'delai_ideal': data.get('delai_ideal'),
			'delai_ideal_autre': data.get('delai_ideal_autre'),
			'recours_sav': data.get('recours_sav'),
			'note_sav': data.get('note_sav'),
			'pieces_non_dispo': data.get('pieces_non_dispo'),
			'experience_satisfait': data.get('experience_satisfait'),
			'personnel_joignable': data.get('personnel_joignable'),
			'note_accueil': data.get('note_accueil'),
			'commande_simple': data.get('commande_simple'),
			'moyen_commande': data.get('moyen_commande'),
			'moyen_commande_autre': data.get('moyen_commande_autre'),
			'suggestions': data.get('suggestions'),
			'motivation_commande': data.get('motivation_commande'),
			'note_recommandation': data.get('note_recommandation'),
		}
		html = render_to_string('front/pdf_satisfaction_b2b.html', {'reponse': reponse})
		result = BytesIO()
		pisa.CreatePDF(html, dest=result)
		pdf_bytes = result.getvalue()
		pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

		from .models import Commercial, Rendezvous
		commercial = Commercial.objects.filter(id=commercial_id).first() if commercial_id else None
		rdv = Rendezvous.objects.filter(uuid=rdv_uuid).first() if rdv_uuid else None

		if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id'))):
			raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")

		# Fonction helper pour convertir en int si possible
		def to_int_or_none(value):
			if value and value.strip():
				try:
					return int(value)
				except (ValueError, TypeError):
					return None
			return None

		# Création de l'objet SatisfactionB2B avec toutes les réponses du formulaire
		SatisfactionB2B.objects.create(
			pdf_base64=pdf_b64,
			rs_nom=rs_nom or "Inconnu",
			commercial=commercial,
			rdv=rdv,
			satisfaction_qualite_pieces=data.get('qualite_satisfait'),
			note_qualite_pieces=to_int_or_none(data.get('note_qualite_globale')),
			probleme_qualite_piece=data.get('probleme_qualite'),
			type_probleme_qualite_piece=data.get('type_probleme'),
			satisfaction_delai_livraison=data.get('delai_satisfait'),
			delai_livraison_moyen=data.get('delai_moyen'),
			delai_livraison_ideal=data.get('delai_ideal'),
			delai_livraison_ideal_autre=data.get('delai_ideal_autre'),
			recours_sav=data.get('recours_sav'),
			note_sav=to_int_or_none(data.get('note_sav')),
			piece_non_dispo=data.get('pieces_non_dispo'),
			satisfaction_experience_rubio=data.get('experience_satisfait'),
			personnel_joignable=data.get('personnel_joignable'),
			note_accueil=to_int_or_none(data.get('note_accueil')),
			commande_simple=data.get('commande_simple'),
			moyen_commande=data.get('moyen_commande'),
			moyen_commande_autre=data.get('moyen_commande_autre'),
			suggestion=data.get('suggestions'),
			motivation_commande=data.get('motivation_commande'),
			note_recommandation=to_int_or_none(data.get('note_recommandation')),
		)
		return render(request, 'front/satisfaction_b2b.html', {'success': True, 'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})
	return render(request, 'front/satisfaction_b2b.html', {'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})	

def check_satisfaction_exists(request, uuid):
	from .models import SatisfactionB2B, Rendezvous
	rdv = Rendezvous.objects.filter(uuid=uuid).first()
	if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id'))):
		raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
	exists = False
	satisfaction_uuid = None
	if rdv:
		satisfaction = SatisfactionB2B.objects.filter(rdv=rdv).first()
		if satisfaction:
			exists = True
			satisfaction_uuid = satisfaction.uuid
	return JsonResponse({'exists': exists, 'satisfaction_uuid': satisfaction_uuid})

def download_satisfaction_pdf(request, uuid):
	from .models import SatisfactionB2B
	satisfaction = SatisfactionB2B.objects.filter(uuid=uuid).first()
	if not satisfaction or not satisfaction.pdf_base64:
		raise Http404("PDF non trouvé")
	# Sécurité : vérifier que l'utilisateur a le droit d'accéder à ce PDF
	rdv = satisfaction.rdv if hasattr(satisfaction, 'rdv') else None
	role = request.session.get('role')
	if rdv and not (
		request.user.is_superuser or
		(rdv.commercial and rdv.commercial.id == request.session.get('commercial_id')) or
		(role in ['responsable', 'admin'])
	):
		raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
	pdf_bytes = base64.b64decode(satisfaction.pdf_base64)
	response = HttpResponse(pdf_bytes, content_type='application/pdf')
	response['Content-Disposition'] = f'inline; filename="satisfaction_{uuid}.pdf"'
	return response

@require_GET
@login_required
def get_client_comments(request, client_id):
	try:
		# On récupère tous les rendez-vous de ce client
		rdvs = Rendezvous.objects.filter(client_id=client_id)
		# On récupère tous les commentaires liés à ces rendez-vous
		commentaires = CommentaireRdv.objects.filter(rdv__in=rdvs).order_by('-date_creation')
		data = []
		
		for c in commentaires:
			try:
				auteur = 'Système'
				if c.commercial:
					auteur = c.commercial.commercial
				elif c.auteur:
					auteur = c.auteur.username
				
				data.append({
					'texte': c.texte,
					'date': c.date_creation.strftime('%d/%m/%Y %H:%M'),
					'auteur': auteur
				})
			except Exception as e:
				print(f"Erreur lors du traitement du commentaire {c.id}: {e}")
				continue
		
		return JsonResponse({'commentaires': data})
	except Exception as e:
		print(f"Erreur dans get_client_comments: {e}")
		return JsonResponse({'commentaires': [], 'error': str(e)})

@login_required
def get_client_rdv(request, client_id):
	statut = request.GET.get('statut')
	qs = Rendezvous.objects.filter(client_id=client_id)
	if statut:
		qs = qs.filter(statut_rdv=statut)
	rdvs = qs.order_by('-date_rdv', '-heure_rdv')
	
	# Récupérer le nom du client
	client = FrontClient.objects.get(id=client_id)
	client_name = f"{client.civilite or ''} {client.rs_nom or '(sans raison sociale)'}".strip()
	
	data = []
	for rdv in rdvs:
		data.append({
			'date_rdv': rdv.date_rdv.strftime('%d/%m/%Y'),
			'heure_rdv': rdv.heure_rdv.strftime('%H:%M') if rdv.heure_rdv else '',
			'statut_rdv': rdv.statut_rdv,
			'commentaire': rdv.notes or '',
			'commercial': str(rdv.commercial),
			'objet': rdv.objet or '',
		})
	
	return JsonResponse({
		'success': True,
		'rdvs': data,
		'client_name': client_name
	})

@login_required
def dashboard_responsable(request):
	# S'assurer que seul un responsable ou admin peut voir cette page
	role = request.session.get('role')
	if role not in ['responsable', 'admin']:
		raise PermissionDenied
	
	# --- Nettoyage automatique des RDV anciens ---
	rdvs_nettoyes = nettoyer_rdv_anciens_automatiquement()
	if rdvs_nettoyes > 0:
		# Stocker l'info pour l'afficher dans le template
		request.session['rdvs_nettoyes'] = rdvs_nettoyes
	# --- Fin nettoyage automatique ---

	commerciaux = Commercial.objects.filter(role='commercial')

	# Récupérer le dernier RDV pour chaque commercial
	for commercial in commerciaux:
		# On ne veut que les RDV validés ou annulés ET déjà passés
		now = timezone.now()
		# On combine date et heure pour comparer à maintenant
		rdvs = Rendezvous.objects.filter(
			commercial=commercial,
			statut_rdv__in=['valide', 'annule']
		)
		dernier_rdv = None
		for rdv in rdvs.order_by('-date_rdv', '-heure_rdv'):
			from datetime import datetime
			dt = datetime.combine(rdv.date_rdv, rdv.heure_rdv)
			if timezone.is_naive(dt):
				dt = timezone.make_aware(dt, timezone.get_current_timezone())
			if dt <= now:
				dernier_rdv = rdv
				break
		commercial.dernier_rdv = dernier_rdv
		if dernier_rdv:
			satisfaction_pdf = SatisfactionB2B.objects.filter(rdv=dernier_rdv).first()
			commercial.dernier_rdv_pdf = satisfaction_pdf
		else:
			commercial.dernier_rdv_pdf = None

	# Récupérer les dernières activités
	latest_activities = ActivityLog.objects.all()[:15]

	# Calculer les moyennes de satisfaction
	satisfactions = SatisfactionB2B.objects.all()
	if satisfactions.exists():
		# Calcul des moyennes pour chaque type de note
		avg_qualite = satisfactions.aggregate(Avg('note_qualite_pieces'))['note_qualite_pieces__avg'] or 0
		avg_sav = satisfactions.aggregate(Avg('note_sav'))['note_sav__avg'] or 0
		avg_accueil = satisfactions.aggregate(Avg('note_accueil'))['note_accueil__avg'] or 0
		avg_recommandation = satisfactions.aggregate(Avg('note_recommandation'))['note_recommandation__avg'] or 0
		
		# Normaliser les notes intelligemment selon leur échelle
		if avg_qualite <= 5:
			avg_qualite_normalisee = avg_qualite * 2  # 1-5 -> 2-10
		else:
			avg_qualite_normalisee = avg_qualite  # Déjà sur 10
		
		if avg_sav <= 5:
			avg_sav_normalisee = avg_sav * 2  # 1-5 -> 2-10
		else:
			avg_sav_normalisee = avg_sav  # Déjà sur 10
		
		if avg_accueil <= 5:
			avg_accueil_normalisee = avg_accueil * 2  # 1-5 -> 2-10
		else:
			avg_accueil_normalisee = avg_accueil  # Déjà sur 10
		
		# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
		avg_recommandation_normalisee = avg_recommandation
		
		# Calculer la moyenne globale sur 10
		moyenne_globale = (avg_qualite_normalisee + avg_sav_normalisee + avg_accueil_normalisee + avg_recommandation_normalisee) / 4
		
		satisfaction_data = {
			'total_responses': satisfactions.count(),
			'average_satisfaction': round(moyenne_globale, 1),
			'satisfaction_percentage': round(moyenne_globale * 10),  # Multiplier par 10 pour avoir le pourcentage
			'trend': 'neutral'  # 'up', 'down', 'neutral'
		}
		
		# Déterminer la tendance
		if moyenne_globale >= 8:
			satisfaction_data['trend'] = 'up'
		elif moyenne_globale < 6:
			satisfaction_data['trend'] = 'down'
		else:
			satisfaction_data['trend'] = 'neutral'
	else:
		satisfaction_data = {
			'total_responses': 0,
			'average_satisfaction': 0,
			'satisfaction_percentage': 0,
			'trend': 'neutral'
		}
		# Initialiser les notes normalisées pour éviter UnboundLocalError
		avg_qualite_normalisee = 0
		avg_sav_normalisee = 0
		avg_accueil_normalisee = 0
		avg_recommandation_normalisee = 0
		moyenne_globale = 0

	chart_data = {
		"labels": ["Qualité pièces", "SAV", "Accueil", "Recommandation"],
		"datasets": [
			{
				"label": "Moyenne des notes",
				"data": [
					avg_qualite_normalisee,
					avg_sav_normalisee,
					avg_accueil_normalisee,
					avg_recommandation_normalisee
				],
				"backgroundColor": [
					"rgba(229, 57, 53, 0.6)",
					"rgba(255, 138, 101, 0.6)", 
					"rgba(255, 209, 128, 0.6)",
					"rgba(120, 144, 156, 0.6)"
				],
				"borderColor": [
					"rgba(229, 57, 53, 1)",
					"rgba(255, 138, 101, 1)",
					"rgba(255, 209, 128, 1)", 
					"rgba(120, 144, 156, 1)"
				],
				"borderWidth": 1,
				"borderRadius": 5
			}
		]
	}

	# Récupérer l'utilisateur connecté
	commercial_id = request.session.get('commercial_id')
	user_commercial = Commercial.objects.get(id=commercial_id)
	
	context = {
		'commerciaux': commerciaux,
		'user_commercial': user_commercial,  # Ajout de l'utilisateur connecté
		'stats_satisfaction_chart': json.dumps(chart_data),
		'latest_activities': latest_activities,
		'conversion_labels': json.dumps([f"{c.prenom} {c.nom}" for c in commerciaux]),
		'conversion_data': json.dumps([
			round((Rendezvous.objects.filter(commercial=c, statut_rdv='valide').count() / max(1, Rendezvous.objects.filter(commercial=c, statut_rdv='a-venir').count())) * 100, 2)
			for c in commerciaux
		]),
	}
	return render(request, 'front/dashboard_responsable.html', context)

@login_required
def api_satisfaction_stats(request):
	commercial_id = request.GET.get('commercial_id')
	start_date_str = request.GET.get('start_date')
	end_date_str = request.GET.get('end_date')
	period = request.GET.get('period')
	granularity = request.GET.get('granularity', 'mois')

	queryset = SatisfactionB2B.objects.all()

	# Filtre par commercial
	if commercial_id and commercial_id != 'all':
		queryset = queryset.filter(commercial_id=commercial_id)

	# Filtre par période
	if start_date_str and end_date_str:
		start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
		end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
		queryset = queryset.filter(date_soumission__date__range=[start_date, end_date])

	# Si aucun filtre de période n'est appliqué, retourner le format initial
	if not start_date_str and not end_date_str and not period:
		# Calculer les moyennes globales
		if queryset.exists():
			moyenne_qualite = queryset.aggregate(Avg('note_qualite_pieces'))['note_qualite_pieces__avg'] or 0
			moyenne_sav = queryset.aggregate(Avg('note_sav'))['note_sav__avg'] or 0
			moyenne_accueil = queryset.aggregate(Avg('note_accueil'))['note_accueil__avg'] or 0
			moyenne_recommandation = queryset.aggregate(Avg('note_recommandation'))['note_recommandation__avg'] or 0
			
			# Normaliser les notes intelligemment selon leur échelle
			if moyenne_qualite <= 5:
				moyenne_qualite = round(moyenne_qualite * 2, 2)  # 1-5 -> 2-10
			else:
				moyenne_qualite = round(moyenne_qualite, 2)  # Déjà sur 10
			
			if moyenne_sav <= 5:
				moyenne_sav = round(moyenne_sav * 2, 2)  # 1-5 -> 2-10
			else:
				moyenne_sav = round(moyenne_sav, 2)  # Déjà sur 10
			
			if moyenne_accueil <= 5:
				moyenne_accueil = round(moyenne_accueil * 2, 2)  # 1-5 -> 2-10
			else:
				moyenne_accueil = round(moyenne_accueil, 2)  # Déjà sur 10
			
			# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
			moyenne_recommandation = round(moyenne_recommandation, 2)
		else:
			moyenne_qualite = moyenne_sav = moyenne_accueil = moyenne_recommandation = 0

		chart_data = {
			"labels": ["Qualité pièces", "SAV", "Accueil", "Recommandation"],
			"datasets": [
				{
					"label": "Moyenne des notes",
					"data": [
						moyenne_qualite,
						moyenne_sav,
						moyenne_accueil,
						moyenne_recommandation
					],
					"backgroundColor": [
						"rgba(229, 57, 53, 0.6)",
						"rgba(255, 138, 101, 0.6)", 
						"rgba(255, 209, 128, 0.6)",
						"rgba(120, 144, 156, 0.6)"
					],
					"borderColor": [
						"rgba(229, 57, 53, 1)",
						"rgba(255, 138, 101, 1)",
						"rgba(255, 209, 128, 1)", 
						"rgba(120, 144, 156, 1)"
					],
					"borderWidth": 1,
					"borderRadius": 5
				}
			]
		}
		return JsonResponse(chart_data)

	# Sinon, retourner les données groupées par période
	# Groupement dynamique
	if granularity == 'jour':
		trunc = TruncDay('date_soumission')
		date_format = '%d/%m/%Y'
	elif granularity == 'semaine':
		trunc = TruncWeek('date_soumission')
		date_format = 'Semaine %W %Y'
	elif granularity == 'annee':
		trunc = TruncYear('date_soumission')
		date_format = '%Y'
	else:  # mois par défaut
		trunc = TruncMonth('date_soumission')
		date_format = '%m/%Y'

	grouped = queryset.annotate(period=trunc).values('period').order_by('period').annotate(
		moyenne_qualite_pieces=Avg('note_qualite_pieces'),
		moyenne_sav=Avg('note_sav'),
		moyenne_accueil=Avg('note_accueil'),
		moyenne_recommandation=Avg('note_recommandation')
	)

	labels = []
	qualite = []
	sav = []
	accueil = []
	recommandation = []
	for entry in grouped:
		period = entry['period']
		if granularity == 'semaine':
			# Affichage semaine : Semaine XX YYYY
			week = period.isocalendar()[1]
			year = period.year
			labels.append(f"Semaine {week} {year}")
		else:
			labels.append(period.strftime(date_format))
		
		# Normaliser les notes intelligemment selon leur échelle
		note_qualite = entry['moyenne_qualite_pieces'] or 0
		note_sav = entry['moyenne_sav'] or 0
		note_accueil = entry['moyenne_accueil'] or 0
		note_recommandation = entry['moyenne_recommandation'] or 0
		
		if note_qualite <= 5:
			qualite.append(round(note_qualite * 2, 2))  # 1-5 -> 2-10
		else:
			qualite.append(round(note_qualite, 2))  # Déjà sur 10
		
		if note_sav <= 5:
			sav.append(round(note_sav * 2, 2))  # 1-5 -> 2-10
		else:
			sav.append(round(note_sav, 2))  # Déjà sur 10
		
		if note_accueil <= 5:
			accueil.append(round(note_accueil * 2, 2))  # 1-5 -> 2-10
		else:
			accueil.append(round(note_accueil, 2))  # Déjà sur 10
		
		# La note de recommandation est déjà sur 10, pas besoin de la multiplier par 2
		recommandation.append(round(note_recommandation, 2))

	chart_data = {
		"labels": labels,
		"datasets": [
			{"label": "Qualité pièces", "data": qualite, "backgroundColor": "rgba(229, 57, 53, 0.6)"},
			{"label": "SAV", "data": sav, "backgroundColor": "rgba(255, 138, 101, 0.6)"},
			{"label": "Accueil", "data": accueil, "backgroundColor": "rgba(255, 209, 128, 0.6)"},
			{"label": "Recommandation", "data": recommandation, "backgroundColor": "rgba(120, 144, 156, 0.6)"},
		]
	}
	return JsonResponse(chart_data)

@login_required
def get_last_rdv_commercial(request, commercial_id):
	commercial = Commercial.objects.get(id=commercial_id)
	dernier_rdv = Rendezvous.objects.filter(
		commercial=commercial,
		statut_rdv__in=['valide', 'annule']
	).order_by('-date_rdv', '-heure_rdv').first()
	if dernier_rdv:
		client, adresse, client_type = get_client_and_adresse(dernier_rdv.client.id)
		return JsonResponse({
			'statut': dernier_rdv.statut_rdv,
			'date': dernier_rdv.date_rdv.strftime('%d/%m/%Y'),
			'heure': dernier_rdv.heure_rdv.strftime('%H:%M'),
			'civilite': getattr(client, 'civilite', ''),
			'rs_nom': getattr(client, 'rs_nom', ''),
		})
	else:
		return JsonResponse({'statut': None})

@login_required
def api_rdv_counters(request):
	now = timezone.now()
	# Pour les RDV réalisés et annulés, on garde le filtre par mois (historique)
	total_realise = Rendezvous.objects.filter(statut_rdv='valide', date_rdv__year=now.year, date_rdv__month=now.month).count()
	total_annule = Rendezvous.objects.filter(statut_rdv='annule', date_rdv__year=now.year, date_rdv__month=now.month).count()
	
	# Pour les RDV à venir, on affiche tous les futurs (pas de filtre par mois)
	total_avenir = Rendezvous.objects.filter(statut_rdv='a_venir', date_rdv__gte=now.date()).count()
	
	return JsonResponse({
		'total_realise': total_realise,
		'total_avenir': total_avenir,
		'total_annule': total_annule,
	})

@login_required
@require_GET
def api_rdvs_a_venir(request):
	role = request.session.get('role')
	commercial_id = request.GET.get('commercial_id')
	# Si responsable/admin, on prend l'id passé en GET, sinon celui de la session
	if role in ['responsable', 'admin'] and commercial_id:
		pass  # on garde commercial_id du GET
	else:
		commercial_id = request.session.get('commercial_id')
	if not commercial_id:
		return JsonResponse({'error': 'Non authentifié'}, status=403)
	rdvs = Rendezvous.objects.filter(commercial_id=commercial_id, statut_rdv='a_venir').order_by('date_rdv', 'heure_rdv')
	data = []
	for rdv in rdvs:
		client, adresse, client_type = get_client_and_adresse(rdv.client.id)
		data.append({
			'uuid': str(rdv.uuid),
			'client': adresse["adresse"] if adresse else getattr(rdv.client, 'rs_nom', ''),
			'civilite': getattr(client, 'civilite', ''),
			'rs_nom': getattr(client, 'rs_nom', ''),
			'date': rdv.date_rdv.strftime('%d/%m/%Y'),
			'heure': rdv.heure_rdv.strftime('%H:%M'),
			'objet': rdv.objet,
			'notes': rdv.notes,
		})
	return JsonResponse({'rdvs': data})

@login_required
@require_GET
def api_rdv_counters_by_client(request):
	"""API pour récupérer le nombre de RDV validés pour un client spécifique"""
	rs_nom = request.GET.get('rs_nom', '').strip()
	if not rs_nom:
		return JsonResponse({'nb_rdv_valides': 0})
	
	# Compter les RDV validés pour ce client
	nb_rdv_valides = Rendezvous.objects.filter(
		client__rs_nom=rs_nom,
		statut_rdv='valide'
	).count()
	
	return JsonResponse({'nb_rdv_valides': nb_rdv_valides})

@require_GET
@login_required
def api_clients_by_commercial(request):
	commercial_id = request.GET.get('commercial_id')
	if not commercial_id:
		return JsonResponse({'clients': []})
	try:
		commercial = Commercial.objects.get(id=commercial_id)
		# On prend le nom de code (ex: "Commercial 1") et on supprime les espaces
		commercial_name = commercial.commercial.replace(' ', '').strip()
		# On cherche les clients avec ce nom de code (insensible à la casse)
		clients = FrontClient.objects.filter(commercial__iexact=commercial_name)
		data = [
			{
				'id': client.id,
				'nom': client.rs_nom or '',
				'prenom': client.prenom or ''
			}
			for client in clients
		]
		return JsonResponse({'clients': data})
	except Commercial.DoesNotExist:
		return JsonResponse({'clients': []})

@csrf_exempt  # À sécuriser en prod !
def import_clients_excel(request):
	if request.method == 'POST' and request.FILES.get('excel_file'):
		excel_file = request.FILES['excel_file']
		try:
			df = pd.read_excel(excel_file)
			commercial_id = request.session.get('commercial_id')
			clients = []
			adresses_data = []
			# On prépare les objets FrontClient sans les enregistrer tout de suite
			for _, row in df.iterrows():
				client = FrontClient(
					nom=row.get('nom', ''),
					prenom=row.get('prenom', ''),
					civilite=row.get('civilite', ''),
					rs_nom=row.get('rs_nom', ''),
					telephone=row.get('telephone', ''),
					statut=row.get('statut', ''),
					en_compte=row.get('en_compte', False) in [True, 'True', '1', 1, 'oui', 'Oui', 'OUI'],
					actif=True,
					code_comptable=row.get('code_comptable', ''),
					email=row.get('email', ''),
					email_comptabilite=row.get('email_comptabilite', ''),
					siret=row.get('siret', ''),
					date_creation=datetime.now(),
					commercial_id=commercial_id,
					commentaires=row.get('commentaires', ''),
					commercial=row.get('commercial', ''),
				)
				clients.append(client)
			# Création en base
			FrontClient.objects.bulk_create(clients)
			# On récupère les clients créés (ordre inverse d'insertion)
			created_clients = list(FrontClient.objects.order_by('-id')[:len(clients)][::-1])
			for i, client in enumerate(created_clients):
				row = df.iloc[i]
				adresse = Adresse(
					client=client,
					adresse=row.get('adresse', ''),
					code_postal=row.get('code_postal', ''),
					ville=row.get('ville', ''),
				)
				adresses_data.append(adresse)
			Adresse.objects.bulk_create(adresses_data)
			return JsonResponse({'message': f'Import réussi ({len(clients)} clients, {len(adresses_data)} adresses)'})
		except Exception as e:
			return JsonResponse({'message': f'Erreur lors de l\'import : {e}'}, status=400)
	return JsonResponse({'message': 'Aucun fichier reçu'}, status=400)

@login_required
def api_commerciaux(request):
	commerciaux = Commercial.objects.filter(role='commercial')
	data = [
		{
			'id': commercial.id,
			'nom': commercial.nom,
			'prenom': commercial.prenom,
			'is_absent': commercial.is_absent
		}
		for commercial in commerciaux
	]
	return JsonResponse({'commerciaux': data})

@login_required
def fiche_commercial_view(request, commercial_id):
	commercial = get_object_or_404(Commercial, id=commercial_id)
	rdvs = Rendezvous.objects.filter(commercial=commercial).select_related('client').order_by('-date_rdv')

	# Filtrer les rendez-vous par statut ET date
	now = timezone.now().date()
	visites_recentes = [r for r in rdvs if r.statut_rdv == 'valide' and r.date_rdv <= now]
	visites_a_venir = [r for r in rdvs if r.statut_rdv == 'a_venir' and r.date_rdv >= now]
	a_rappeler = [r for r in rdvs if r.statut_rdv == 'annule']

	total_realise = len(visites_recentes)
	total_avenir = len(visites_a_venir)
	total_annule = len(a_rappeler)

	# Ajout du compteur de rendez-vous validés pour chaque rdv (comme sur le dashboard)
	for rdv in visites_recentes + a_rappeler:
		rdv.nb_rdv_valides = Rendezvous.objects.filter(
			client=rdv.client,
			commercial=rdv.commercial,
			statut_rdv='valide'
		).count()

	# Calcul des données de satisfaction client
	satisfactions = SatisfactionB2B.objects.filter(commercial=commercial)
	satisfaction_data = {
		'total_responses': satisfactions.count(),
		'average_satisfaction': 0,
		'satisfaction_percentage': 0,
		'trend': 'neutral',  # 'up', 'down', 'neutral'
		'monthly_comparison': 0,
		'yearly_comparison': 0,
		'current_month_score': 0,
		'previous_month_score': 0,
		'current_year_score': 0,
		'previous_year_score': 0
	}
	
	if satisfactions.exists():
		# Utiliser le nouveau score hybride au lieu de l'ancien calcul
		from .utils import calculate_comprehensive_satisfaction_score
		
		# Calculer le score hybride pour chaque satisfaction
		hybrid_scores = []
		for satisfaction in satisfactions:
			try:
				score = calculate_comprehensive_satisfaction_score(satisfaction)
				hybrid_scores.append(score)
			except Exception as e:
				# En cas d'erreur, utiliser le score hybride stocké en base
				if satisfaction.score_hybride:
					hybrid_scores.append(float(satisfaction.score_hybride))
				else:
					# Fallback sur l'ancien système
					avg_qualite = satisfaction.note_qualite_pieces or 0
					avg_sav = satisfaction.note_sav or 0
					avg_accueil = satisfaction.note_accueil or 0
					avg_recommandation = satisfaction.note_recommandation or 0
					
					if any([avg_qualite, avg_sav, avg_accueil, avg_recommandation]):
						avg_qualite_normalisee = avg_qualite * 2
						avg_sav_normalisee = avg_sav * 2
						avg_accueil_normalisee = avg_accueil * 2
						moyenne_globale = (avg_qualite_normalisee + avg_sav_normalisee + avg_accueil_normalisee + avg_recommandation) / 4
						hybrid_scores.append(moyenne_globale)
		
		# Calculer la moyenne des scores hybrides
		if hybrid_scores:
			moyenne_globale = sum(hybrid_scores) / len(hybrid_scores)
		else:
			moyenne_globale = 0
		
		satisfaction_data['average_satisfaction'] = round(moyenne_globale, 1)
		satisfaction_data['satisfaction_percentage'] = round(moyenne_globale * 10)  # Multiplier par 10 pour avoir le pourcentage
		
		# Calcul des comparaisons mensuelles et annuelles
		from datetime import datetime, timedelta
		# from django.utils import timezone  # SUPPRIMÉ car déjà importé en haut
		
		now = timezone.now()
		
		# Périodes pour les comparaisons
		current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
		previous_month_end = current_month_start - timedelta(microseconds=1)
		
		current_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
		previous_year_start = current_year_start.replace(year=current_year_start.year - 1)
		previous_year_end = current_year_start - timedelta(microseconds=1)
		
		# Calcul des scores par période
		def calculate_period_score(satisfactions_period):
			if not satisfactions_period.exists():
				return 0
			
			period_scores = []
			for satisfaction in satisfactions_period:
				try:
					score = calculate_comprehensive_satisfaction_score(satisfaction)
					period_scores.append(score)
				except Exception as e:
					if satisfaction.score_hybride:
						period_scores.append(float(satisfaction.score_hybride))
			
			return sum(period_scores) / len(period_scores) if period_scores else 0
		
		# Scores par période
		current_month_satisfactions = satisfactions.filter(date_soumission__gte=current_month_start)
		previous_month_satisfactions = satisfactions.filter(
			date_soumission__gte=previous_month_start,
			date_soumission__lte=previous_month_end
		)
		
		current_year_satisfactions = satisfactions.filter(date_soumission__gte=current_year_start)
		previous_year_satisfactions = satisfactions.filter(
			date_soumission__gte=previous_year_start,
			date_soumission__lte=previous_year_end
		)
		
		# Calcul des scores
		current_month_score = calculate_period_score(current_month_satisfactions)
		previous_month_score = calculate_period_score(previous_month_satisfactions)
		current_year_score = calculate_period_score(current_year_satisfactions)
		previous_year_score = calculate_period_score(previous_year_satisfactions)
		
		# Comparaisons (convertir en pourcentage)
		monthly_comparison = (current_month_score - previous_month_score) * 10
		yearly_comparison = (current_year_score - previous_year_score) * 10
		
		# Stockage des données
		satisfaction_data.update({
			'monthly_comparison': round(monthly_comparison, 1),
			'yearly_comparison': round(yearly_comparison, 1),
			'current_month_score': round(current_month_score, 1),
			'previous_month_score': round(previous_month_score, 1),
			'current_year_score': round(current_year_score, 1),
			'previous_year_score': round(previous_year_score, 1)
		})
		
		# Déterminer la tendance (basée sur la comparaison mensuelle)
		if monthly_comparison > 0.5:
			satisfaction_data['trend'] = 'up'
		elif monthly_comparison < -0.5:
			satisfaction_data['trend'] = 'down'
		else:
			satisfaction_data['trend'] = 'neutral'

	context = {
		'commercial': commercial,
		'visites_recentes': visites_recentes,
		'visites_a_venir': visites_a_venir,
		'a_rappeler': a_rappeler,
		'total_realise': total_realise,
		'total_avenir': total_avenir,
		'total_annule': total_annule,
		'satisfaction_data': satisfaction_data,
		'role': getattr(request.user, 'role', '')
	}
	return render(request, 'front/fiche_commercial.html', context)

@login_required
def export_satisfactions_excel(request):
	data = SatisfactionB2B.objects.all().values()
	import pandas as pd
	df = pd.DataFrame(list(data))
	# Supprimer la colonne pdf_base64 si elle existe
	if 'pdf_base64' in df.columns:
		df = df.drop(columns=['pdf_base64'])
	# Rendre toutes les dates timezone-unaware (naive)
	for col in df.columns:
		if pd.api.types.is_datetime64_any_dtype(df[col]):
			df[col] = df[col].apply(lambda x: x.tz_localize(None) if hasattr(x, 'tz_localize') and x is not None else x)
	response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = 'attachment; filename="satisfactions.xlsx"'
	df.to_excel(response, index=False)
	return response

@require_GET
def search_clients(request):
	q = request.GET.get('q', '').strip()
	if not q:
		return JsonResponse({'results': []})
	
	# Optimisation : Utiliser only() pour récupérer seulement les champs nécessaires
	qs = FrontClient.objects.filter(
		Q(rs_nom__icontains=q) |
		Q(prenom__icontains=q) |
		Q(civilite__icontains=q)
	).only('civilite', 'rs_nom', 'prenom')[:15]  # Limite à 15 résultats
	
	results = [
		{
			'civilite': c.civilite or '',
			'rs_nom': c.rs_nom or '',
			'prenom': c.prenom or ''
		}
		for c in qs
	]
	return JsonResponse({'results': results})

@require_GET
def search_clients_table(request):
	q = request.GET.get('q', '').strip()
	if not q:
		return JsonResponse({'results': []})
	
	# Optimisation : Utiliser select_related pour éviter les requêtes N+1
	clients = FrontClient.objects.filter(
		Q(rs_nom__icontains=q) |
		Q(prenom__icontains=q) |
		Q(civilite__icontains=q)
	).prefetch_related('adresses')[:50]  # Limite à 50 résultats pour la performance
	
	results = []
	for c in clients:
		adresse_obj = c.adresses.first()  # Utilise la relation préchargée
		results.append({
			'civilite': c.civilite or '',
			'rs_nom': c.rs_nom or '',
			'prenom': c.prenom or '',
			'adresse': adresse_obj.adresse if adresse_obj else '',
			'code_postal': adresse_obj.code_postal if adresse_obj else '',
			'ville': adresse_obj.ville if adresse_obj else ''
		})
	return JsonResponse({'results': results})

# === Fonctions utilitaires safe pour la migration ===
def get_client_and_adresse(client_id):
	"""
	Récupère un client et son adresse de façon sécurisée, en privilégiant FrontClient/Adresse,
	avec fallback sur ImportClientCorrected si besoin.
	"""
	from .models import FrontClient, Adresse, ImportClientCorrected
	try:
		client = FrontClient.objects.get(id=client_id)
		adresse_obj = Adresse.objects.filter(client=client).first()
		adresse = {
			"adresse": adresse_obj.adresse if adresse_obj else "",
			"code_postal": adresse_obj.code_postal if adresse_obj else "",
			"ville": adresse_obj.ville if adresse_obj else "",
		}
		client_type = "front"
		
		# Enrichir le client avec les informations manquantes
		if not hasattr(client, 'email') or not client.email:
			client.email = getattr(client, 'email', '')
		if not hasattr(client, 'civilite'):
			client.civilite = ''
		if not hasattr(client, 'statut'):
			client.statut = ''
		if not hasattr(client, 'code_comptable'):
			client.code_comptable = ''
		if not hasattr(client, 'classement_client'):
			client.classement_client = ''
			
	except FrontClient.DoesNotExist:
		# Fallback temporaire
		client = ImportClientCorrected.objects.get(id=client_id)
		adresse = {
			"adresse": client.adresse,
			"code_postal": client.code_postal,
			"ville": client.ville,
		}
		client_type = "import"
		
		# Enrichir le client import avec les informations manquantes
		if not hasattr(client, 'email') or not client.email:
			client.email = getattr(client, 'e_mail', '')
		if not hasattr(client, 'civilite'):
			client.civilite = ''
		if not hasattr(client, 'statut'):
			client.statut = ''
		if not hasattr(client, 'code_comptable'):
			client.code_comptable = ''
		if not hasattr(client, 'classement_client'):
			client.classement_client = ''
			
	return client, adresse, client_type

# === Remplacement dans les vues ===
# Exemple pour add_rdv (à adapter pour chaque vue concernée)
# ... existing code ...
# Remplacer :
# client = ImportClientCorrected.objects.get(id=client_id)
# par :
# client, adresse, client_type = get_client_and_adresse(client_id)
# Utiliser ensuite client.rs_nom, adresse["adresse"], etc.
# ... existing code ...

def politique_confidentialite(request):
	role = request.session.get('role', '')
	return render(request, 'front/politique_confidentialite.html', {'role': role})

@login_required
def mentions_legales(request):
	role = request.session.get('role', '')
	return render(request, 'front/mentions_legales.html', {'role': role})

def mentions_legales(request):
	return render(request, 'front/mentions_legales.html')

# Nouvelles vues pour l'optimisation de trajet
@login_required
def route_optimisee(request):
	"""Vue pour afficher la page de route optimisée"""
	commercial_id = request.session.get('commercial_id')
	if not commercial_id:
		return redirect('login')
	
	commercial = Commercial.objects.get(id=commercial_id)
	
	# Date par défaut (aujourd'hui)
	from datetime import date
	default_date = date.today().strftime('%Y-%m-%d')
	
	return render(request, 'front/route_optimisee.html', {
		'commercial': commercial,
		'default_date': default_date
	})

@login_required
def api_route_optimisee(request, date):
	"""API pour récupérer la route optimisée pour une date donnée"""
	commercial_id = request.session.get('commercial_id')
	if not commercial_id:
		return JsonResponse({'error': 'Non autorisé'}, status=401)
	
	try:
		commercial = Commercial.objects.get(id=commercial_id)
		from .services import RouteOptimizationService
		
		route_data = RouteOptimizationService.get_optimized_route_for_commercial(commercial, date)
		
		# Préparer les données pour le template
		rdvs_data = []
		for rdv in route_data['rdvs']:
			address = None
			if rdv.client:
				address = rdv.client.adresses.filter(
					latitude__isnull=False,
					longitude__isnull=False
				).first()
			
			rdvs_data.append({
				'id': rdv.id,
				'uuid': str(rdv.uuid),
				'client_name': rdv.client.rs_nom if rdv.client else 'Client inconnu',
				'heure': rdv.heure_rdv.strftime('%H:%M'),
				'objet': rdv.objet or '',
				'address': address,
				'latitude': float(address.latitude) if address else None,
				'longitude': float(address.longitude) if address else None,
			})
		
		return JsonResponse({
			'success': True,
			'rdvs': rdvs_data,
			'total_distance': route_data['total_distance'],
			'estimated_time_minutes': route_data['estimated_time_minutes']
		})
		
	except Commercial.DoesNotExist:
		return JsonResponse({'error': 'Commercial non trouvé'}, status=404)
	except Exception as e:
		return JsonResponse({'error': str(e)}, status=500)

@login_required
def geocoder_adresses(request):
	"""Vue pour déclencher le géocodage des adresses"""
	if request.method == 'POST':
		try:
			from .services import GeocodingService
			GeocodingService.geocode_all_addresses()
			return JsonResponse({'success': True, 'message': 'Géocodage terminé avec succès'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return render(request, 'front/geocoder_adresses.html')

from django.http import JsonResponse

@login_required
def api_search_rdv_historique(request):
	query = request.GET.get('q', '').strip().lower()
	if not query:
		return JsonResponse({'results': []})

	# On cherche dans les clients liés à des rendez-vous archivés
	rdvs = Rendezvous.objects.filter(
		statut_rdv__in=['valide', 'annule']
	).select_related('client')

	seen_clients = set()
	results = []
	for rdv in rdvs:
		client = rdv.client
		if not client or client.id in seen_clients:
			continue
		# Champs à rechercher
		nom = (getattr(client, 'nom', '') or '').lower()
		prenom = (getattr(client, 'prenom', '') or '').lower()
		rs_nom = (getattr(client, 'rs_nom', '') or '').lower()
		# Match sur nom, prénom, raison sociale
		if query in nom or query in prenom or query in rs_nom:
			label = client.rs_nom or f"{client.nom or ''} {client.prenom or ''}".strip()
			results.append({
				'client_id': client.id,
				'label': label,
			})
			seen_clients.add(client.id)
			if len(results) >= 10:
				break
	return JsonResponse({'results': results})

@csrf_exempt
def extend_session(request):
    """Vue pour prolonger la session utilisateur"""
    if request.method == 'POST':
        if 'commercial_id' in request.session:
            # Mettre à jour le timestamp de dernière activité
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Supprimer les flags d'alerte
            if 'show_timeout_warning' in request.session:
                del request.session['show_timeout_warning']
            if 'timeout_warning_minutes' in request.session:
                del request.session['timeout_warning_minutes']
            
            return JsonResponse({'success': True, 'message': 'Session prolongée'})
        else:
            return JsonResponse({'success': False, 'message': 'Utilisateur non connecté'}, status=401)
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)
