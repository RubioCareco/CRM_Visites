from django.shortcuts import render, redirect, get_object_or_404
from .models import Commercial, Client, Rendezvous, CommentaireRdv, ImportClientCorrected, SatisfactionB2B
from django.contrib.auth.hashers import check_password, make_password
from functools import wraps
from django.http import JsonResponse, HttpResponse, Http404
from datetime import datetime
from django.utils import timezone
import json
from django.core.mail import send_mail
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
                notes=request.POST.get('notes'),
                statut_rdv='a_venir'  # Par défaut, à venir
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
def update_statut(request, uuid, statut):
    print("DEBUG méthode reçue :", request.method)
    rdv = get_object_or_404(Rendezvous, uuid=uuid)
    if not (request.user.is_superuser or (rdv.commercial and rdv.commercial.user == request.user)):
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
        if not (request.user.is_superuser or (rdv.commercial and rdv.commercial.user == request.user)):
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

        if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.user == request.user)):
            raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")

        SatisfactionB2B.objects.create(
            pdf_base64=pdf_b64,
            rs_nom=rs_nom or "Inconnu",
            commercial=commercial,
            rdv=rdv
        )
        return render(request, 'front/satisfaction_b2b.html', {'success': True, 'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})
    return render(request, 'front/satisfaction_b2b.html', {'note_recommandation_choices': note_recommandation_choices, 'rs_nom': rs_nom})    

def check_satisfaction_exists(request, uuid):
    from .models import SatisfactionB2B, Rendezvous
    rdv = Rendezvous.objects.filter(uuid=uuid).first()
    if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.user == request.user)):
        raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
    exists = False
    if rdv:
        exists = SatisfactionB2B.objects.filter(rdv=rdv).exists()
    return JsonResponse({'exists': exists})

def download_satisfaction_pdf(request, uuid):
    from .models import SatisfactionB2B, Rendezvous
    rdv = Rendezvous.objects.filter(uuid=uuid).first()
    if rdv and not (request.user.is_superuser or (rdv.commercial and rdv.commercial.user == request.user)):
        raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce rendez-vous.")
    satisfaction = SatisfactionB2B.objects.filter(rdv=rdv).first() if rdv else None
    if not satisfaction or not satisfaction.pdf_base64:
        raise Http404("PDF non trouvé")
    pdf_bytes = base64.b64decode(satisfaction.pdf_base64)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="satisfaction_{uuid}.pdf"'
    return response
