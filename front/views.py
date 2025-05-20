from django.shortcuts import render, redirect, get_object_or_404
from .models import Commercial, Client, Rendezvous, CommentaireRdv
from django.contrib.auth.hashers import check_password
from functools import wraps
from django.http import JsonResponse
from datetime import datetime
from django.utils import timezone
import json

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
            return redirect('dashboard')
        else:
            erreur = True
    return render(request, 'front/login.html', {'erreur': erreur})

# 🔐 Déconnexion
def logout_view(request):
    request.session.flush()
    return redirect('login')

@login_required
def reset_password(request):
    return render(request, 'front/reset_password.html')

@login_required
def new_password(request):
    return render(request, 'front/new_password.html')

@login_required
def reset_password(request):
    return render(request, 'front/reset_password.html')

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
            client = Client.objects.get(id=client_id)

            Rendezvous.objects.create(
                client=client,
                commercial=commercial,
                date_rdv=request.POST.get('date_rdv'),
                heure_rdv=request.POST.get('heure_rdv'),
                objet=request.POST.get('objet'),
                notes=request.POST.get('notes')
            )
            return redirect('dashboard')

        except Exception as e:
            print("❌ Erreur :", e)

    clients = Client.objects.all()
    client_temp = request.session.get('client_temp') if from_new_client else None
    next_url = request.GET.get('next', '/dashboard')

    return render(request, 'front/add_rdv.html', {
        'clients': clients,
        'client_temp': client_temp,
        'next': next_url,
        'from_new_client': from_new_client
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
        elif statut == "annuler":
            rdv.notes = f"Annulé - {commentaire}"

        rdv.save()

        client_name = rdv.client.entreprise or rdv.client.nom
        date_formatted = rdv.date_rdv.strftime('%d/%m/%Y')

        return JsonResponse({
            'status': 'ok',
            'id': rdv.id,
            'nom': client_name,
            'date': date_formatted,
            'statut': statut
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
            'entreprise': client.entreprise,
            'nom': client.nom,
            'prenom': client.prenom,
            'adresse': client.adresse,
            'code_postal': client.code_postal,
            'date': rdv.date_rdv.strftime('%d/%m/%Y'),
            'heure': rdv.heure_rdv.strftime('%H:%M'),
            'commentaires': commentaires_data
        })
    except Rendezvous.DoesNotExist:
        return JsonResponse({'error': 'Rendez-vous introuvable'}, status=404)
