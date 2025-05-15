from django.shortcuts import render

# Create your views here.
def login_view(request):
    return render(request, 'front/login.html')

def reset_password(request):
    return render(request, 'front/reset_password.html')

def new_password(request):
    return render(request, 'front/new_password.html')

def dashboard(request):
    return render(request, 'front/dashboard.html')

def new_client(request):
    return render(request, 'front/new_client.html')

def add_rdv(request):
    return render(request, 'front/add_rdv.html')

def profil(request):
    return render(request, 'front/profil.html')
