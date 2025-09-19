from django.contrib import admin
from .models import (
    Commercial,
    Rendezvous,
    CommentaireRdv,
    FrontClient,
    Adresse,
    SatisfactionB2B,
    ActivityLog,
    ClientVisitStats,
)
from django.contrib.auth.hashers import make_password

class CommercialAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email')

    def save_model(self, request, obj, form, change):
        # Si le mot de passe a été modifié (ou nouvel objet)
        if 'password' in form.changed_data or not obj.pk:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

# admin.site.unregister(Commercial)  # <-- À retirer ou commenter
admin.site.register(Commercial, CommercialAdmin)
admin.site.register(Rendezvous)
admin.site.register(CommentaireRdv)


@admin.register(FrontClient)
class FrontClientAdmin(admin.ModelAdmin):
    list_display = ("id", "rs_nom", "commercial", "commercial_id", "classement_client", "actif")
    list_filter = ("actif", "classement_client")
    search_fields = ("rs_nom", "commercial", "code_comptable")


@admin.register(Adresse)
class AdresseAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "adresse", "code_postal", "ville", "latitude", "longitude", "geocode_date")
    search_fields = ("adresse", "code_postal", "ville", "client__rs_nom")
    list_filter = ("ville",)


@admin.register(SatisfactionB2B)
class SatisfactionB2BAdmin(admin.ModelAdmin):
    list_display = ("id", "rs_nom", "commercial", "rdv", "date_soumission", "moyenne", "score_hybride")
    search_fields = ("rs_nom",)
    list_filter = ("date_soumission",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "commercial", "action_type", "description", "timestamp")
    list_filter = ("action_type", "timestamp")
    search_fields = ("description", "commercial__nom", "commercial__prenom")


@admin.register(ClientVisitStats)
class ClientVisitStatsAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "commercial", "annee", "visites_valides", "objectif")
    list_filter = ("annee",)
    search_fields = ("client__rs_nom", "commercial__nom", "commercial__prenom")
