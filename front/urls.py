from django.urls import path
from . import views
from django.contrib.auth.models import User
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.login_view, name='home'),  # Route pour la page principale
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new-client/', views.new_client, name='new_client'),
    path('add-rdv/', views.add_rdv, name='add_rdv'),
    path('profil/', views.profil, name='profil'),
    path('customer-file/', views.customer_file, name='customer_file'),
    path('logout/', views.logout_view, name='logout'),
    path('delete-temp-rdv', views.delete_temp_rdv, name='delete_temp_rdv'),
    path('update-statut/<uuid:uuid>/<str:statut>/', views.update_statut, name='update_statut_rdv'),
    path('get-rdv-info/<uuid:uuid>/', views.get_rdv_info, name='get_rdv_info'),
    path('client-file/', views.client_file, name='client_file'),
    path('historique-rdv/', views.historique_rdv, name='historique_rdv'),
    path('update-client/<int:client_id>/', views.update_client, name='update_client'),
    path('check-satisfaction/<uuid:uuid>/', views.check_satisfaction_exists, name='check_satisfaction'),
    path('download-satisfaction/<uuid:uuid>/', views.download_satisfaction_pdf, name='download_satisfaction_pdf'),
    path('get-client-comments/<int:client_id>/', views.get_client_comments, name='get_client_comments'),
    path('dashboard-responsable/', views.dashboard_responsable, name='dashboard_responsable'),
    path('check-satisfaction-exists/<uuid:uuid>/', views.check_satisfaction_exists, name='check_satisfaction_exists'),
    path('get-last-rdv-commercial/<int:commercial_id>/', views.get_last_rdv_commercial, name='get_last_rdv_commercial'),
    path('api/rdv-counters/', views.api_rdv_counters, name='api_rdv_counters'),
    path('api/rdvs-a-venir/', views.api_rdvs_a_venir, name='api_rdvs_a_venir'),
    path('api/clients-by-commercial/', views.api_clients_by_commercial, name='api_clients_by_commercial'),
    path('import-clients-excel/', views.import_clients_excel, name='import_clients_excel'),
]
