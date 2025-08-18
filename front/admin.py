from django.contrib import admin
from .models import Commercial, Rendezvous, CommentaireRdv
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
