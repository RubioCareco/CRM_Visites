from django.shortcuts import render, redirect
from .models import Commercial
from django.contrib.auth.hashers import check_password
from functools import wraps


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


# 🏠 Dashboard
@login_required
def dashboard(request):
    return render(request, 'front/dashboard.html')


# 🔄 Pages classiques
def reset_password(request):
    return render(request, 'front/reset_password.html')

def new_password(request):
    return render(request, 'front/new_password.html')

@login_required
def new_client(request):
    return render(request, 'front/new_client.html')

@login_required
def add_rdv(request):
    if request.method == 'POST':
        next_url = request.POST.get('next') or '/dashboard'
        return redirect(next_url)

    next_url = request.GET.get('next', '/dashboard')
    return render(request, 'front/add_rdv.html', {'next': next_url})


# 👤 Vue Profil : affichage + édition
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
        return redirect('profil')  # Pour rafraîchir la page avec les nouvelles données

    return render(request, 'front/profil.html', {'commercial': commercial})


# 📁 Fiche client
@login_required
def customer_file(request):
    return render(request, 'front/customer_file.html')
