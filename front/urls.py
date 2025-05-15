from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='home'),  # Route pour la page principale
    path('login/', views.login_view, name='login'),
     path('reset-password/', views.reset_password, name='reset_password'),
     path('new-password/', views.new_password, name='new_password'),
     path('dashboard/', views.dashboard, name='dashboard'),
     path('new-client/', views.new_client, name='new_client'),
     path('add-rdv/', views.add_rdv, name='add_rdv'),
     path('profil/', views.profil, name='profil') 
]
