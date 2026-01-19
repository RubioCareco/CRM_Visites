# front/admin.py
from django.contrib import admin
from django.contrib.auth.hashers import make_password, identify_hasher
from django.http import HttpResponse
import csv

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

# =========================
# Inlines
# =========================
class AdresseInline(admin.TabularInline):
    model = Adresse
    extra = 0
    fields = ("adresse", "code_postal", "ville", "latitude", "longitude", "geocode_date")
    readonly_fields = ("geocode_date",)


# =========================
# Commercial
# =========================
@admin.register(Commercial)
class CommercialAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "email")
    search_fields = ("nom", "prenom", "email")
    list_filter = ("is_absent",)  # laisse si le champ existe dans ton modèle

    def save_model(self, request, obj, form, change):
        """
        Hash le mot de passe si et seulement s'il n'est PAS déjà un hash Django.
        Évite le 'double hash' si un admin réenregistre la fiche telle quelle.
        """
        pwd = getattr(obj, "password", None)
        if pwd:
            try:
                # Si c'est déjà un hash Django valide -> ne pas rehasher
                identify_hasher(pwd)
                already_hashed = True
            except Exception:
                already_hashed = False
            if not already_hashed:
                obj.password = make_password(pwd)
        super().save_model(request, obj, form, change)


# =========================
# Actions RDV
# =========================
def mark_annule(modeladmin, request, queryset):
    queryset.update(statut_rdv="annule")
mark_annule.short_description = 'Marquer "annulé"'

def mark_valide(modeladmin, request, queryset):
    queryset.update(statut_rdv="valide")
mark_valide.short_description = 'Marquer "validé"'

def export_csv(modeladmin, request, queryset):
    """
    Exporte une sélection de RDV en CSV (simple et efficace).
    """
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="rendezvous.csv"'
    writer = csv.writer(resp)
    writer.writerow(["id", "date", "heure", "commercial", "client", "statut", "objet"])
    for o in queryset.select_related("commercial", "client"):
        writer.writerow([
            o.id,
            o.date_rdv,
            o.heure_rdv,
            getattr(o.commercial, "commercial", o.commercial),  # affiche le nom d'usage si dispo
            getattr(o.client, "rs_nom", o.client),
            o.statut_rdv,
            o.objet,
        ])
    return resp
export_csv.short_description = "Exporter en CSV"


# =========================
# Rendezvous
# =========================
@admin.register(Rendezvous)
class RendezvousAdmin(admin.ModelAdmin):
    list_display = ("date_rdv", "heure_rdv", "commercial", "client", "statut_rdv")
    list_filter = ("statut_rdv", "commercial", "date_rdv")
    search_fields = ("client__rs_nom", "objet")
    date_hierarchy = "date_rdv"
    ordering = ("-date_rdv", "-heure_rdv")
    list_select_related = ("commercial", "client")
    actions = [mark_annule, mark_valide, export_csv]
    # autocomplete_fields = ("client", "commercial")


# =========================
# FrontClient
# =========================
@admin.register(FrontClient)
class FrontClientAdmin(admin.ModelAdmin):
    list_display = ("id", "rs_nom", "commercial", "commercial_id", "classement_client", "actif")
    list_filter = ("actif", "classement_client")
    search_fields = ("rs_nom", "commercial", "code_comptable")
    inlines = [AdresseInline]
    ordering = ("rs_nom",)


# =========================
# Adresse
# =========================
@admin.register(Adresse)
class AdresseAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "adresse", "code_postal", "ville", "latitude", "longitude", "geocode_date")
    search_fields = ("adresse", "code_postal", "ville", "client__rs_nom")
    list_filter = ("ville",)
    list_select_related = ("client",)


# =========================
# Commentaire RDV
# =========================
@admin.register(CommentaireRdv)
class CommentaireRdvAdmin(admin.ModelAdmin):
    list_display = ("id", "rdv", "auteur", "date_creation", "short_texte")
    list_select_related = ("rdv", "auteur", "commercial")
    search_fields = ("texte", "rs_nom", "rdv__objet", "auteur__username", "auteur__first_name", "auteur__last_name")
    date_hierarchy = "date_creation"
    ordering = ("-date_creation",)

    def short_texte(self, obj):
        txt = obj.texte or ""
        return (txt[:80] + "…") if len(txt) > 80 else txt
    short_texte.short_description = "texte"
    short_texte.admin_order_field = "texte"


# =========================
# Satisfaction B2B
# =========================
@admin.register(SatisfactionB2B)
class SatisfactionB2BAdmin(admin.ModelAdmin):
    list_display = ("id", "rs_nom", "commercial", "rdv", "date_soumission", "moyenne", "score_hybride")
    search_fields = ("rs_nom",)
    list_filter = ("date_soumission",)


# =========================
# Activity Log
# =========================
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "commercial", "action_type", "description", "timestamp")
    list_filter = ("action_type", "timestamp")
    search_fields = ("description", "commercial__nom", "commercial__prenom")


# =========================
# ClientVisitStats
# =========================
@admin.register(ClientVisitStats)
class ClientVisitStatsAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "commercial", "annee", "visites_valides", "objectif")
    list_filter = ("annee",)
    search_fields = ("client__rs_nom", "commercial__nom", "commercial__prenom")
