from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import json

class SessionTimeoutMiddleware:
    """
    Middleware pour déconnecter automatiquement les utilisateurs après 30 minutes d'inactivité
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # 30 minutes d'inactivité
        self.timeout_minutes = 30
        # 5 minutes avant expiration pour afficher l'alerte
        self.warning_minutes = 5
        
    def __call__(self, request):
        # Vérifier si l'utilisateur est connecté
        if 'commercial_id' in request.session:
            # Récupérer le timestamp de dernière activité
            last_activity = request.session.get('last_activity')
            current_time = timezone.now()
            
            if last_activity:
                # Convertir le timestamp en datetime
                last_activity = timezone.datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                
                # Calculer le temps écoulé
                time_elapsed = current_time - last_activity
                timeout_delta = timedelta(minutes=self.timeout_minutes)
                warning_delta = timedelta(minutes=self.timeout_minutes - self.warning_minutes)
                
                # Vérifier si la session a expiré
                if time_elapsed >= timeout_delta:
                    # Session expirée - déconnecter l'utilisateur
                    request.session.flush()
                    messages.warning(request, 'Votre session a expiré après 30 minutes d\'inactivité. Veuillez vous reconnecter.')
                    return redirect('login')
                
                # Vérifier si on doit afficher l'alerte
                elif time_elapsed >= warning_delta:
                    # Ajouter un flag pour afficher l'alerte
                    request.session['show_timeout_warning'] = True
                    request.session['timeout_warning_minutes'] = self.timeout_minutes - int(time_elapsed.total_seconds() / 60)
            
            # Mettre à jour le timestamp de dernière activité
            request.session['last_activity'] = current_time.isoformat()
            
            # Supprimer le flag d'alerte si l'utilisateur est actif
            if 'show_timeout_warning' in request.session:
                del request.session['show_timeout_warning']
                if 'timeout_warning_minutes' in request.session:
                    del request.session['timeout_warning_minutes']
        
        response = self.get_response(request)
        return response


class SecurityHeadersMiddleware:
    """Apply configurable browser security headers not covered by default middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        coop = getattr(settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY", None)
        coep = getattr(settings, "SECURE_CROSS_ORIGIN_EMBEDDER_POLICY", None)

        if coop and "Cross-Origin-Opener-Policy" not in response:
            response["Cross-Origin-Opener-Policy"] = coop
        if coep and "Cross-Origin-Embedder-Policy" not in response:
            response["Cross-Origin-Embedder-Policy"] = coep

        return response
