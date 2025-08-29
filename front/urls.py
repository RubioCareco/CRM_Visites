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
    path('profil/<int:commercial_id>/', views.profil, name='profil_commercial'),
    path('profils-commerciaux/', views.profils_commerciaux, name='profils_commerciaux'),
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
    path('download-satisfaction-pdf/<uuid:uuid>/', views.download_satisfaction_pdf, name='download_satisfaction_pdf_alt'),
    path('get-client-comments/<int:client_id>/', views.get_client_comments, name='get_client_comments'),
    path('dashboard-responsable/', views.dashboard_responsable, name='dashboard_responsable'),
    path('check-satisfaction-exists/<uuid:uuid>/', views.check_satisfaction_exists, name='check_satisfaction_exists'),
    path('get-last-rdv-commercial/<int:commercial_id>/', views.get_last_rdv_commercial, name='get_last_rdv_commercial'),
    path('api/rdv-counters/', views.api_rdv_counters, name='api_rdv_counters'),
    path('api/rdv-counters-by-client/', views.api_rdv_counters_by_client, name='api_rdv_counters_by_client'),
    path('api/rdvs-a-venir/', views.api_rdvs_a_venir, name='api_rdvs_a_venir'),
    path('api/clients-by-commercial/', views.api_clients_by_commercial, name='api_clients_by_commercial'),
    path('import-clients-excel/', views.import_clients_excel, name='import_clients_excel'),
    path('historique-rdv-responsable/', views.historique_rdv_resp, name='historique_rdv_resp'),
    path('api/commerciaux/', views.api_commerciaux, name='api_commerciaux'),
    path('fiche-commercial/<int:commercial_id>/', views.fiche_commercial_view, name='fiche_commercial'),
    path('api/satisfaction-stats/', views.api_satisfaction_stats, name='api_satisfaction_stats'),
    path('export-satisfactions-excel/', views.export_satisfactions_excel, name='export_satisfactions_excel'),
    path('search-clients/', views.search_clients, name='search_clients'),
    path('search-clients-table/', views.search_clients_table, name='search_clients_table'),
    path('get_client_rdv/<int:client_id>/', views.get_client_rdv, name='get_client_rdv'),
    path('politique-confidentialite', views.politique_confidentialite, name='politique_confidentialite'),
    path('mentions-legales', views.mentions_legales, name='mentions_legales'),
    path('new-password/', views.new_password, name='new_password'),
    # Nouvelles URLs pour l'optimisation de trajet
    path('route-optimisee/', views.route_optimisee, name='route_optimisee'),
    path('api/route-optimisee/<str:date>/', views.api_route_optimisee, name='api_route_optimisee'),
    path('geocoder-adresses/', views.geocoder_adresses, name='geocoder_adresses'),
    path('api/search-rdv-historique/', views.api_search_rdv_historique, name='api_search_rdv_historique'),
    path('extend-session/', views.extend_session, name='extend_session'),
]
