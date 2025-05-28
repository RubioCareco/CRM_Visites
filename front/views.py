from django.shortcuts import render, redirect, get_object_or_404
from .models import Commercial, Client, Rendezvous, CommentaireRdv, ImportClientCorrected
from django.contrib.auth.hashers import check_password, make_password
from functools import wraps
from django.http import JsonResponse
from datetime import datetime
from django.utils import timezone
import json
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import models
from django.core.paginator import Paginator

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
            send_mail(
                'Réinitialisation de mot de passe',
                f'Cliquez sur ce lien pour réinitialiser votre mot de passe : {reset_link}',
                'no-reply@crm.local',
                [email],
            )
            reset_links.append(reset_link)
        for commercial in commercials:
            token = get_random_string(48)
            reset_tokens[token] = ('commercial', commercial.id)
            reset_link = request.build_absolute_uri(reverse('new_password')) + f'?token={token}'
            send_mail(
                'Réinitialisation de mot de passe',
                f'Cliquez sur ce lien pour réinitialiser votre mot de passe : {reset_link}',
                'no-reply@crm.local',
                [email],
            )
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
        dt_rdv = datetime.combine(rdv.date_rdv, rdv.heure_rdv)
        if timezone.is_naive(dt_rdv):
            dt_rdv = timezone.make_aware(dt_rdv)

        notes = (rdv.notes or '').lower()

        if 'validé' in notes:
            visites_recentes.append(rdv)
        elif 'annulé' in notes:
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
            client_prefill = ImportClientCorrected.objects.get(id=client_id_prefill, commercial__iexact=commercial.commercial)
        except ImportClientCorrected.DoesNotExist:
            client_prefill = None

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

            client_id = request.POST.get('client_id')
            client = ImportClientCorrected.objects.get(id=client_id, commercial__iexact=commercial.commercial)

            Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=request.POST.get('date_rdv'),
                heure_rdv=request.POST.get('heure_rdv'),
                objet=request.POST.get('objet'),
                notes=request.POST.get('notes')
            )
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard')

        except Exception as e:
            print("❌ Erreur :", e)

    clients = ImportClientCorrected.objects.filter(commercial__iexact=commercial.commercial)
    client_temp = request.session.get('client_temp') if from_new_client else None
    next_url = request.GET.get('next', '/dashboard')

    return render(request, 'front/add_rdv.html', {
        'clients': clients,
        'client_temp': client_temp,
        'next': next_url,
        'from_new_client': from_new_client,
        'client_prefill': client_prefill,
    })

# 📁 Fiche client
@login_required
def customer_file(request):
    return render(request, 'front/customer_file.html')

# 👤 Profil commercial
@login_required
def profil(request):
    commercial_id = request.session.get('commercial_id')
    commercial = Commercial.objects.get(id=commercial_id)

    if request.method == 'POST':
        commercial.nom = request.POST.get('nom') or commercial.nom
        commercial.prenom = request.POST.get('prenom') or commercial.prenom
        commercial.email = request.POST.get('email') or commercial.email
        commercial.telephone = request.POST.get('telephone') or commercial.telephone
        commercial.save()
        return redirect('profil')

    return render(request, 'front/profil.html', {'commercial': commercial})

# ❌ Supprimer le rdv temporaire
@login_required
def delete_temp_rdv(request):
    request.session.pop('rdv_temp', None)
    return JsonResponse({'status': 'ok'})

# ✅ Mise à jour du statut via modal dynamique
@login_required
def update_statut(request, rdv_id, statut):
    rdv = get_object_or_404(Rendezvous, id=rdv_id)

    if request.method == 'POST':
        data = json.loads(request.body)
        commentaire = data.get('commentaire', '')

        if statut == "valider":
            rdv.notes = f"Validé - {commentaire}"
            rdv.date_statut = timezone.now()
        elif statut == "annuler":
            rdv.notes = f"Annulé - {commentaire}"
            rdv.date_statut = timezone.now()

        rdv.save()

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
            'statut': getattr(client, 'statut', ''),
            'date': rdv.date_rdv.strftime('%d/%m/%Y'),
            'heure': rdv.heure_rdv.strftime('%H:%M'),
            'date_statut': rdv.date_statut.strftime('%d/%m/%Y %H:%M') if rdv.date_statut else '',
        })

    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=400)

from django.http import JsonResponse

@login_required
def get_rdv_info(request, rdv_id):
    try:
        rdv = Rendezvous.objects.get(id=rdv_id)
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

    # Récupérer le commercial connecté
    commercial_nom = request.session.get('commercial_nom')
    print("DEBUG - commercial_nom en session :", commercial_nom)  # Debug

    if not commercial_nom:
        clients_qs = ImportClientCorrected.objects.none()
    else:
        clients_qs = ImportClientCorrected.objects.filter(commercial__iexact=commercial_nom)

    paginator = Paginator(clients_qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(request, 'front/Client_file.html', {
        'page_obj': page_obj,
        'per_page': per_page,
        'paginator': paginator,
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
        notes = (rdv.notes or '').lower()
        if 'validé' in notes:
            visites_recentes.append(rdv)
            historique_general.append(rdv)
        elif 'annulé' in notes:
            a_rappeler.append(rdv)
            historique_general.append(rdv)
    # On trie l'historique général par date décroissante (déjà fait par la requête)
    return render(request, 'front/historique_rdv.html', {
        'commercial': commercial,
        'visites_recentes': visites_recentes,
        'a_rappeler': a_rappeler,
        'historique_general': historique_general,
    })    
