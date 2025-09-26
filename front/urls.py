# front/urls.py

from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Racine → /login/
    path("", RedirectView.as_view(url="/login/", permanent=False), name="home"),

    # Connexion/Deconnexion
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Tableaux de bord
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard-responsable/", views.dashboard_responsable, name="dashboard_responsable"),

    # Clients / RDV
    path("new-client/", views.new_client, name="new_client"),
    path("add-rdv/", views.add_rdv, name="add_rdv"),
    path("delete-temp-rdv", views.delete_temp_rdv, name="delete_temp_rdv"),
    path("update-statut/<uuid:uuid>/<str:statut>/", views.update_statut, name="update_statut_rdv"),
    path("get-rdv-info/<uuid:uuid>/", views.get_rdv_info, name="get_rdv_info"),
    path("client-file/", views.client_file, name="client_file"),
    path("customer-file/", views.customer_file, name="customer_file"),
    path("update-client/<int:client_id>/", views.update_client, name="update_client"),
    path("get_client_rdv/<int:client_id>/", views.get_client_rdv, name="get_client_rdv"),
    path("get-last-rdv-commercial/<int:commercial_id>/", views.get_last_rdv_commercial, name="get_last_rdv_commercial"),

    # Profils
    path("profil/", views.profil, name="profil"),
    path("profil/<int:commercial_id>/", views.profil, name="profil_commercial"),
    path("profils-commerciaux/", views.profils_commerciaux, name="profils_commerciaux"),
    path("fiche-commercial/<int:commercial_id>/", views.fiche_commercial_view, name="fiche_commercial"),

    # Historique / recherche
    path("historique-rdv/", views.historique_rdv, name="historique_rdv"),
    path("historique-rdv-responsable/", views.historique_rdv_resp, name="historique_rdv_resp"),
    path("search-clients/", views.search_clients, name="search_clients"),
    path("search-clients-table/", views.search_clients_table, name="search_clients_table"),
    path("api/search-rdv-historique/", views.api_search_rdv_historique, name="api_search_rdv_historique"),

    # APIs
    path("api/rdv-counters/", views.api_rdv_counters, name="api_rdv_counters"),
    path("api/rdv-counters-by-client/", views.api_rdv_counters_by_client, name="api_rdv_counters_by_client"),
    path("api/rdvs-a-venir/", views.api_rdvs_a_venir, name="api_rdvs_a_venir"),
    path("api/clients-by-commercial/", views.api_clients_by_commercial, name="api_clients_by_commercial"),
    path("api/commerciaux/", views.api_commerciaux, name="api_commerciaux"),
    path("api/satisfaction-stats/", views.api_satisfaction_stats, name="api_satisfaction_stats"),
    path("api/client-details/<int:client_id>/", views.api_client_details, name="api_client_details"),

    # Satisfactions
    path("check-satisfaction/<uuid:uuid>/", views.check_satisfaction_exists, name="check_satisfaction"),
    path("check-satisfaction-exists/<uuid:uuid>/", views.check_satisfaction_exists, name="check_satisfaction_exists"),
    path("download-satisfaction/<uuid:uuid>/", views.download_satisfaction_pdf, name="download_satisfaction_pdf"),
    path("download-satisfaction-pdf/<uuid:uuid>/", views.download_satisfaction_pdf, name="download_satisfaction_pdf_alt"),

    # Divers
    path("import-clients-excel/", views.import_clients_excel, name="import_clients_excel"),
    path("politique-confidentialite", views.politique_confidentialite, name="politique_confidentialite"),
    path("mentions-legales", views.mentions_legales, name="mentions_legales"),
    path("extend-session/", views.extend_session, name="extend_session"),
    path("objectif-annuel/", views.objectif_annuel, name="objectif_annuel"),

    # Mots de passe
    path("new-password/", views.new_password, name="new_password"),

    # Optimisation de trajet
    path("route-optimisee/", views.route_optimisee, name="route_optimisee"),
    path("api/route-optimisee/<str:date>/", views.api_route_optimisee, name="api_route_optimisee"),

    # Géocodage
    path("geocoder-adresses/", views.geocoder_adresses, name="geocoder_adresses"),
]
