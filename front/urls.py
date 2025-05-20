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
     path('profil/', views.profil, name='profil'),
     path('customer-file/', views.customer_file, name='customer_file'),
     path('logout/', views.logout_view, name='logout'),
     path('delete-temp-rdv', views.delete_temp_rdv, name='delete_temp_rdv'),
     path('update-statut/<int:rdv_id>/<str:statut>/', views.update_statut, name='update_statut_rdv'),
     path('get-rdv-info/<int:rdv_id>/', views.get_rdv_info, name='get_rdv_info'),

]
