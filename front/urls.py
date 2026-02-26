from django.urls import path
from . import views

urlpatterns = [
    path("api/tournee/replace/", views.api_replace_tournee, name="api_replace_tournee"),

    # Auth
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login_page'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboards
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard-test/', views.dashboard_test, name='dashboard_test'),
    path('dashboard-responsable/', views.dashboard_responsable, name='dashboard_responsable'),

    # Clients & RDV
    path('new-client/', views.new_client, name='new_client'),
    path('add-rdv/', views.add_rdv, name='add_rdv'),
    path('delete-temp-rdv/', views.delete_temp_rdv, name='delete_temp_rdv'),

    path('client-file/', views.client_file, name='client_file'),
    path('customer-file/', views.customer_file, name='customer_file'),

    path('historique-rdv/', views.historique_rdv, name='historique_rdv'),
    path('historique-rdv-resp/', views.historique_rdv_resp, name='historique_rdv_resp'),

    # Profil / commerciaux
    path('profils-commerciaux/', views.profils_commerciaux, name='profils_commerciaux'),
    path('profil/', views.profil, name='profil'),
    path('profil/<int:commercial_id>/', views.profil, name='profil_commercial'),
    path('fiche-commercial/<int:commercial_id>/', views.fiche_commercial_view, name='fiche_commercial'),

    # Satisfaction B2B
    path('satisfaction-b2b/', views.satisfaction_b2b, name='satisfaction_b2b'),
    path('check-satisfaction/<uuid:uuid>/', views.check_satisfaction_exists, name='check_satisfaction_exists'),
    path('check-satisfaction-exists/<uuid:uuid>', views.check_satisfaction_exists, name='check_satisfaction_exists_alias'),
    path('download-satisfaction/<uuid:uuid>/', views.download_satisfaction_pdf, name='download_satisfaction_pdf'),
    path('export-satisfactions-excel/', views.export_satisfactions_excel, name='export_satisfactions_excel'),

    # Objectifs annuels
    path('objectif-annuel/', views.objectif_annuel, name='objectif_annuel'),

    # Reset mot de passe
    path('reset-password/', views.reset_password, name='reset_password'),
    path('new-password/', views.new_password, name='new_password'),

    # Optimisation de trajet / géocodage
    path('route-optimisee/', views.route_optimisee, name='route_optimisee'),
    path('api/route-optimisee/<str:date>/', views.api_route_optimisee, name='api_route_optimisee'),
    path('geocoder-adresses/', views.geocoder_adresses, name='geocoder_adresses'),

    # API RDV / stats / clients
    path('api/rdvs-by-date/', views.api_rdvs_by_date, name='api_rdvs_by_date'),
    path('api/capacity/', views.api_capacity, name='api_capacity'),

    path('api/rdv-counters/', views.api_rdv_counters, name='api_rdv_counters'),
    path('api/rdvs-a-venir/', views.api_rdvs_a_venir, name='api_rdvs_a_venir'),
    path('api/rdvs-overdue-count/', views.api_rdvs_overdue_count, name='api_rdvs_overdue_count'),
    path('api/rdv-counters-by-client/', views.api_rdv_counters_by_client, name='api_rdv_counters_by_client'),

    path('api/clients-by-commercial/', views.api_clients_by_commercial, name='api_clients_by_commercial'),
    path('api/commerciaux/', views.api_commerciaux, name='api_commerciaux'),
    path('api/insee/siret/<str:siret>/', views.api_insee_siret, name='api_insee_siret'),

    path('api/map-tournee/', views.api_map_tournee, name='api_map_tournee'),


    path('api/last-rdv-commercial/<int:commercial_id>/', views.get_last_rdv_commercial, name='get_last_rdv_commercial'),

    path('api/satisfaction-stats/', views.api_satisfaction_stats, name='api_satisfaction_stats'),

    path('api/search-rdv-historique/', views.api_search_rdv_historique, name='api_search_rdv_historique'),

    path('api/client-details/uuid/<uuid:client_uuid>/', views.api_client_details_uuid, name='api_client_details_uuid'),

    path('api/client-comments/uuid/<uuid:client_uuid>/', views.api_client_comments_uuid, name='get_client_comments_uuid'),
    path('api/comment-pin/<int:comment_id>/', views.set_comment_pin, name='set_comment_pin'),
    path('api/toggle-pin-comment/<int:comment_id>/', views.toggle_pin_comment, name='toggle_pin_comment'),
    path('api/client-rdv/uuid/<uuid:client_uuid>/', views.get_client_rdv_uuid, name='get_client_rdv_uuid'),

    path('api/clients-import-excel/', views.import_clients_excel, name='import_clients_excel'),

    # Mise à jour client
    path('update-client/uuid/<uuid:client_uuid>/', views.update_client_uuid, name='update_client_uuid'),

    # Update statut RDV / infos RDV
    path('update-statut/<uuid:uuid>/<str:statut>/', views.update_statut, name='update_statut'),
    path('get-rdv-info/<uuid:uuid>/', views.get_rdv_info, name='get_rdv_info'),

    # Recherche clients (autocomplétion + table)
    path('search-clients/', views.search_clients, name='search_clients'),
    path('search-clients-table/', views.search_clients_table, name='search_clients_table'),

    # Divers / légaux
    path('politique-confidentialite/', views.politique_confidentialite, name='politique_confidentialite'),
    path('mentions-legales/', views.mentions_legales, name='mentions_legales'),

    # Session keep-alive
    path('extend-session/', views.extend_session, name='extend_session'),

    # Map
    path('commercial/map/', views.commercial_map, name='commercial_map'),

    # Unpin
    path('rdv/unpin-comment/', views.unpin_comment, name='unpin_comment'),

    path("healthz", views.healthz, name="healthz"),
]
