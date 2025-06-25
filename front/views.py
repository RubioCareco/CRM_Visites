from django.shortcuts import render, redirect, get_object_or_404
from .models import Commercial, Client, Rendezvous, CommentaireRdv, ImportClientCorrected, SatisfactionB2B, FrontClient, ActivityLog
from django.contrib.auth.hashers import check_password, make_password
from functools import wraps
from django.http import JsonResponse, HttpResponse, Http404
from datetime import datetime, timedelta
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
from django.db.models import Avg, Count
from django.db.models.functions import Coalesce, TruncDay, TruncWeek, TruncMonth, TruncYear

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
            subject = 'Réinitialisation de mot de passe'
            text_content = f'''Bonjour,\n\nVous avez demandé la réinitialisation de votre mot de passe.\n\nCliquez sur le lien ci-dessous pour choisir un nouveau mot de passe :\n{reset_link}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n— L'équipe CRM'''
            html_content = f'''<p>Bonjour,</p><p>Vous avez demandé la réinitialisation de votre mot de passe.</p><p>Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe :<br><a href="{reset_link}">Réinitialiser mon mot de passe</a></p><p>Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p><p>— L'équipe CRM</p>'''
            msg = EmailMultiAlternatives(subject, text_content, 'bznjamin.gillens@gmail.com', [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            reset_links.append(reset_link)
        for commercial in commercials:
            token = get_random_string(48)
            reset_tokens[token] = ('commercial', commercial.id)
            reset_link = request.build_absolute_uri(reverse('new_password')) + f'?token={token}'
            subject = 'Réinitialisation de mot de passe'
            text_content = f'''Bonjour,\n\nVous avez demandé la réinitialisation de votre mot de passe.\n\nCliquez sur le lien ci-dessous pour choisir un nouveau mot de passe :\n{reset_link}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n— L'équipe CRM'''
            html_content = f'''<p>Bonjour,</p><p>Vous avez demandé la réinitialisation de votre mot de passe.</p><p>Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe :<br><a href="{reset_link}">Réinitialiser mon mot de passe</a></p><p>Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p><p>— L'équipe CRM</p>'''
            msg = EmailMultiAlternatives(subject, text_content, 'bznjamin.gillens@gmail.com', [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            reset_links.append(reset_link)
        # Pour debug local, on affiche le dernier lien généré
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
    commercial_id = request.session.get('commercial_id')
    commercial = Commercial.objects.get(id=commercial_id)
    now = timezone.now()

    visites_recentes = []
    a_venir = []
    a_rappeler = []

    rdvs = Rendezvous.objects.filter(commercial=commercial).order_by('-date_rdv', '-heure_rdv')

    for rdv in rdvs:
        if rdv.statut_rdv == 'valide':
            visites_recentes.append(rdv)
        elif rdv.statut_rdv == 'annule':
            a_rappeler.append(rdv)
        else:
            a_venir.append(rdv)

    return render(request, 'front/dashboard.html', {
        'commercial': commercial,
        'visites_recentes': visites_recentes,
        'rdvs_a_venir': a_venir,
        'a_rappeler': a_rappeler,
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
                'email': request.POST.get('email'),
                'telephone': request.POST.get('telephone')
            }
            return redirect('/add-rdv?from=new-client')

        temp_data = request.session.get('client_temp') or {}
        nom = request.POST.get('nom') or temp_data.get('nom')
        prenom = request.POST.get('prenom') or temp_data.get('prenom')
        entreprise = request.POST.get('entreprise') or temp_data.get('entreprise')
        siret = request.POST.get('siret') or temp_data.get('siret')
        adresse = request.POST.get('adresse') or temp_data.get('adresse')
        code_postal = request.POST.get('code_postal') or temp_data.get('code_postal')
        email = request.POST.get('email') or temp_data.get('email')
        telephone = request.POST.get('telephone') or temp_data.get('telephone')

        client = Client.objects.create(
            nom=nom,
            prenom=prenom,
            entreprise=entreprise,
            siret=siret,
            adresse=adresse,
            code_postal=code_postal,
            email=email,
            telephone=telephone,
            commercial=commercial
        )

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

        request.session.pop('client_temp', None)
        request.session.pop('rdv_temp', None)

        return redirect('dashboard')

    client_temp = request.session.get('client_temp')
    rdv_temp = request.session.get('rdv_temp')
    return render(request, 'front/new_client.html', {
        'client_temp': client_temp,
        'rdv_temp': rdv_temp
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
            client_prefill = ImportClientCorrected.objects.get(id=client_id_prefill)
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
            client = ImportClientCorrected.objects.get(id=client_id)

            Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=request.POST.get('date_rdv'),
                heure_rdv=request.POST.get('heure_rdv'),
                objet=request.POST.get('objet'),
                notes=request.POST.get('notes'),
                statut_rdv='a_venir'  # Par défaut, à venir
            )

            # Enregistrer l'activité dans le journal
            ActivityLog.objects.create(
                commercial=commercial,
                action_type='RDV_AJOUTE',
                description=f'Nouveau RDV ajouté pour {client.rs_nom}'
            )

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
        commercial.save()

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

    return render(request, 'front/profil.html', {
        'commercial': commercial, 
        'role': request.session.get('role'),
        'can_edit': can_edit
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
                client = rdv.client
                rs_nom = getattr(client, 'rs_nom', None) or getattr(client, 'nom', None) or ''
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
                client = rdv.client
                rs_nom = getattr(client, 'rs_nom', None) or getattr(client, 'nom', None) or ''
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
                client = rdv.client
                rs_nom = getattr(client, 'rs_nom', None) or getattr(client, 'nom', None) or ''
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
        client = rdv.client
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
            'entreprise': getattr(client, 'rs_nom', ''),
            'nom': getattr(client, 'prénom', ''),
            'prenom': getattr(client, 'prénom', ''),
            'adresse': getattr(client, 'adresse', ''),
            'code_postal': getattr(client, 'code_postal', ''),
            'ville': getattr(client, 'ville', ''),
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
    
    # Récupérer la liste des commerciaux pour le sélecteur (uniquement pour les responsables/admins)
    commerciaux = None
    if role in ['responsable', 'admin']:
        commerciaux = Commercial.objects.filter(role='commercial')

    # Filtrage des clients
    clients_qs = ImportClientCorrected.objects.all()
    selected_commercial = request.GET.get('commercial') # Le nom du commercial depuis l'URL

    if role in ['responsable', 'admin']:
        if selected_commercial:
            clients_qs = clients_qs.filter(commercial__iexact=selected_commercial)
    else: # Pour un commercial normal, on filtre sur son propre nom
        commercial_nom = request.session.get('commercial_nom')
        if commercial_nom:
            # Normalisation : suppression des espaces et mise en majuscules
            nom_normalise = commercial_nom.replace(' ', '').upper()
            # On filtre tous les clients dont le champ commercial (après normalisation) correspond
            clients_qs = clients_qs.extra(where=["REPLACE(UPPER(commercial), ' ', '') = %s"], params=[nom_normalise])

    paginator = Paginator(clients_qs.order_by('rs_nom'), per_page)
    page_obj = paginator.get_page(page_number)

    return render(request, 'front/Client_file.html', {
        'page_obj': page_obj,
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
    # On trie l'historique général par date décroissante (déjà fait par la requête)
    return render(request, 'front/historique_rdv.html', {
        'commercial': commercial,
        'visites_recentes': visites_recentes,
        'a_rappeler': a_rappeler,
        'historique_general': historique_general,
        'role': request.session.get('role'),
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
                # Pour les RDV annulés, filtrer sur date_statut (date d'annulation)
                if date_debut_obj:
                    rdvs_archives = rdvs_archives.filter(
                        statut_rdv='annule',
                        date_statut__date__gte=date_debut_obj
                    )
                if date_fin_obj:
                    rdvs_archives = rdvs_archives.filter(
                        statut_rdv='annule',
                        date_statut__date__lt=date_fin_obj
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
    
    # Tri du plus récent au plus ancien
    visites_recentes = sorted(visites_recentes, key=lambda r: (r.date_rdv, r.heure_rdv), reverse=True)
    a_rappeler = sorted(a_rappeler, key=lambda r: (r.date_rdv, r.heure_rdv), reverse=True)

    # Ajout de la date de dernière visite pour chaque rdv
    for rdv in historique_general:
        last_rdv = Rendezvous.objects.filter(
            client=rdv.client,
            commercial=rdv.commercial,
            statut_rdv__in=['valide', 'annule'],
            date_rdv__lt=rdv.date_rdv
        ).order_by('-date_rdv', '-heure_rdv').first()
        rdv.derniere_visite = last_rdv.date_rdv if last_rdv else None
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

    return render(request, 'front/historique_rdv_resp.html', {
        'visites_recentes': visites_recentes,
        'a_rappeler': a_rappeler,
        'historique_general': historique_general,
        'role': request.session.get('role'),
    })

@csrf_exempt  # À remplacer par @login_required + gestion CSRF si besoin
def update_client(request, client_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            client = ImportClientCorrected.objects.get(pk=client_id)
            client.adresse = data.get("adresse", client.adresse)
            client.code_postal = data.get("code_postal", client.code_postal)
            client.ville = data.get("ville", client.ville)
            client.telephone = data.get("telephone", client.telephone)
            client.e_mail = data.get("email", client.e_mail)
            client.save()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Méthode non autorisée"})    

def satisfaction_b2b(request):
    note_recommandation_choices = list(range(1, 11))
    rs_nom = request.GET.get('rs_nom') or request.POST.get('rs_nom')
    commercial_id = request.GET.get('commercial_id') or request.POST.get('commercial_id')
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

        # Création de l'objet SatisfactionB2B avec toutes les réponses du formulaire
        SatisfactionB2B.objects.create(
            pdf_base64=pdf_b64,
            rs_nom=rs_nom or "Inconnu",
            commercial=commercial,
            rdv=rdv,
            satisfaction_qualite_pieces=data.get('qualite_satisfait'),
            note_qualite_pieces=data.get('note_qualite_globale'),
            probleme_qualite_piece=data.get('probleme_qualite'),
            type_probleme_qualite_piece=data.get('type_probleme'),
            satisfaction_delai_livraison=data.get('delai_satisfait'),
            delai_livraison_moyen=data.get('delai_moyen'),
            delai_livraison_ideal=data.get('delai_ideal'),
            delai_livraison_ideal_autre=data.get('delai_ideal_autre'),
            recours_sav=data.get('recours_sav'),
            note_sav=data.get('note_sav'),
            piece_non_dispo=data.get('pieces_non_dispo'),
            satisfaction_experience_rubio=data.get('experience_satisfait'),
            personnel_joignable=data.get('personnel_joignable'),
            note_accueil=data.get('note_accueil'),
            commande_simple=data.get('commande_simple'),
            moyen_commande=data.get('moyen_commande'),
            moyen_commande_autre=data.get('moyen_commande_autre'),
            suggestion=data.get('suggestions'),
            motivation_commande=data.get('motivation_commande'),
            note_recommandation=data.get('note_recommandation'),
        )
        return render(request, 'front/satisfaction_b2b.html', {'success': True, 'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})
    return render(request, 'front/satisfaction_b2b.html', {'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})    

def check_satisfaction_exists(request, uuid):
    from .models import SatisfactionB2B, Rendezvous
    rdv = Rendezvous.objects.filter(uuid=uuid).first()
    if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id'))):
        raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
    exists = False
    if rdv:
        exists = SatisfactionB2B.objects.filter(rdv=rdv).exists()
    return JsonResponse({'exists': exists})

def download_satisfaction_pdf(request, uuid):
    from .models import SatisfactionB2B, Rendezvous
    rdv = Rendezvous.objects.filter(uuid=uuid).first()
    role = request.session.get('role')
    if rdv and not (
        request.user.is_superuser or
        (rdv.commercial and rdv.commercial.id == request.session.get('commercial_id')) or
        (role in ['responsable', 'admin'])
    ):
        raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
    satisfaction = SatisfactionB2B.objects.filter(rdv=rdv).first() if rdv else None
    if not satisfaction or not satisfaction.pdf_base64:
        raise Http404("PDF non trouvé")
    pdf_bytes = base64.b64decode(satisfaction.pdf_base64)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="satisfaction_{uuid}.pdf"'
    return response

@require_GET
@login_required
def get_client_comments(request, client_id):
    # On récupère tous les rendez-vous de ce client
    rdvs = Rendezvous.objects.filter(client_id=client_id)
    # On récupère tous les commentaires liés à ces rendez-vous
    commentaires = CommentaireRdv.objects.filter(rdv__in=rdvs).order_by('-date_creation')
    data = [
        {
            'texte': c.texte,
            'date': c.date_creation.strftime('%d/%m/%Y %H:%M'),
            'auteur': c.commercial.commercial if c.commercial else (c.auteur.username if c.auteur else 'Système')
        }
        for c in commentaires
    ]
    return JsonResponse({'commentaires': data})

@login_required
def dashboard_responsable(request):
    # S'assurer que seul un responsable ou admin peut voir cette page
    role = request.session.get('role')
    if role not in ['responsable', 'admin']:
        raise PermissionDenied

    commerciaux = Commercial.objects.filter(role='commercial')

    # Récupérer le dernier RDV pour chaque commercial
    for commercial in commerciaux:
        dernier_rdv = Rendezvous.objects.filter(
            commercial=commercial, 
            statut_rdv__in=['valide', 'annule']
        ).order_by('-date_rdv', '-heure_rdv').first()
        commercial.dernier_rdv = dernier_rdv
        if dernier_rdv:
            satisfaction_pdf = SatisfactionB2B.objects.filter(rdv=dernier_rdv).first()
            commercial.dernier_rdv_pdf = satisfaction_pdf
        else:
            commercial.dernier_rdv_pdf = None

    # Récupérer les dernières activités
    latest_activities = ActivityLog.objects.all()[:5]

    # Calculer les moyennes de satisfaction
    satisfaction_data = SatisfactionB2B.objects.all()
    if satisfaction_data.exists():
        moyenne_qualite = satisfaction_data.aggregate(Avg('note_qualite_pieces'))['note_qualite_pieces__avg'] or 0
        moyenne_sav = satisfaction_data.aggregate(Avg('note_sav'))['note_sav__avg'] or 0
        moyenne_accueil = satisfaction_data.aggregate(Avg('note_accueil'))['note_accueil__avg'] or 0
        moyenne_recommandation = satisfaction_data.aggregate(Avg('note_recommandation'))['note_recommandation__avg'] or 0
        
        # Normaliser les notes sur 5 vers une échelle de 10
        moyenne_qualite = round(moyenne_qualite * 2, 2)
        moyenne_sav = round(moyenne_sav * 2, 2)
        moyenne_accueil = round(moyenne_accueil * 2, 2)
        # La recommandation est déjà sur 10, pas besoin de conversion
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

    context = {
        'commerciaux': commerciaux,
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
        
        # Normaliser les notes sur 5 vers une échelle de 10
        qualite.append(round((entry['moyenne_qualite_pieces'] or 0) * 2, 2))
        sav.append(round((entry['moyenne_sav'] or 0) * 2, 2))
        accueil.append(round((entry['moyenne_accueil'] or 0) * 2, 2))
        # La recommandation est déjà sur 10, pas besoin de conversion
        recommandation.append(round(entry['moyenne_recommandation'] or 0, 2))

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
        client = dernier_rdv.client
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
    total_realise = Rendezvous.objects.filter(statut_rdv='valide', date_rdv__year=now.year, date_rdv__month=now.month).count()
    total_avenir = Rendezvous.objects.filter(statut_rdv='a_venir', date_rdv__year=now.year, date_rdv__month=now.month).count()
    total_annule = Rendezvous.objects.filter(statut_rdv='annule', date_rdv__year=now.year, date_rdv__month=now.month).count()
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
        client = rdv.client
        data.append({
            'uuid': str(rdv.uuid),
            'client': str(client.rs_nom) if client else '',
            'civilite': getattr(client, 'civilite', ''),
            'rs_nom': getattr(client, 'rs_nom', ''),
            'date': rdv.date_rdv.strftime('%d/%m/%Y'),
            'heure': rdv.heure_rdv.strftime('%H:%M'),
            'objet': rdv.objet,
            'notes': rdv.notes,
        })
    return JsonResponse({'rdvs': data})

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
        clients = ImportClientCorrected.objects.filter(commercial__iexact=commercial_name)
        data = [
            {
                'id': client.id,
                'nom': client.rs_nom or '',
                'prenom': client.prénom or ''
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
            for _, row in df.iterrows():
                clients.append(FrontClient(
                    nom=row.get('nom', ''),
                    prenom=row.get('prenom', ''),
                    entreprise=row.get('entreprise', ''),
                    siret=row.get('siret', ''),
                    adresse=row.get('adresse', ''),
                    code_postal=row.get('code_postal', ''),
                    email=row.get('email', ''),
                    telephone=row.get('telephone', ''),
                    date_creation=datetime.now(),
                    commercial_id=commercial_id,
                    commentaires=row.get('commentaires', ''),
                ))
            FrontClient.objects.bulk_create(clients)
            return JsonResponse({'message': f'Import réussi ({len(clients)} clients)'})
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
            'prenom': commercial.prenom
        }
        for commercial in commerciaux
    ]
    return JsonResponse({'commerciaux': data})

@login_required
def fiche_commercial_view(request, commercial_id):
    commercial = get_object_or_404(Commercial, id=commercial_id)
    rdvs = Rendezvous.objects.filter(commercial=commercial).select_related('client').order_by('-date_rdv')

    visites_recentes = [r for r in rdvs if r.statut_rdv == 'valide' and r.date_rdv <= timezone.now().date()]
    visites_a_venir = [r for r in rdvs if r.date_rdv > timezone.now().date()]
    a_rappeler = [r for r in rdvs if r.statut_rdv == 'annule']

    total_realise = len(visites_recentes)
    total_avenir = len(visites_a_venir)
    total_annule = len(a_rappeler)

    context = {
        'commercial': commercial,
        'visites_recentes': visites_recentes,
        'visites_a_venir': visites_a_venir,
        'a_rappeler': a_rappeler,
        'total_realise': total_realise,
        'total_avenir': total_avenir,
        'total_annule': total_annule,
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
