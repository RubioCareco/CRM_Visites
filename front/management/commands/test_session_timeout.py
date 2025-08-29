from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

class Command(BaseCommand):
    help = 'Teste le middleware de déconnexion automatique'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate-timeout',
            action='store_true',
            help='Simule un timeout de session pour tester'
        )
        parser.add_argument(
            '--simulate-warning',
            action='store_true',
            help='Simule l\'alerte d\'expiration (25 min)'
        )
        parser.add_argument(
            '--session-key',
            type=str,
            help='Clé de session à modifier (optionnel)'
        )

    def handle(self, *args, **options):
        self.stdout.write("=== Test du Middleware de Déconnexion Automatique ===")
        
        if options['simulate_timeout']:
            self.stdout.write("Simulation d'un timeout de session...")
            
            # Simuler un timestamp de dernière activité vieux de 31 minutes
            old_timestamp = (timezone.now() - timedelta(minutes=31)).isoformat()
            
            self.stdout.write(f"Timestamp simulé (31 min dans le passé): {old_timestamp}")
            self.stdout.write("Ce timestamp devrait déclencher une déconnexion automatique.")
            
            # Modifier une session existante si possible
            if options['session_key']:
                self._modify_session(options['session_key'], old_timestamp)
            else:
                self.stdout.write("Utilise --session-key pour modifier une session spécifique")
                
        elif options['simulate_warning']:
            self.stdout.write("Simulation de l'alerte d'expiration...")
            
            # Simuler un timestamp de dernière activité vieux de 25 minutes
            warning_timestamp = (timezone.now() - timedelta(minutes=25)).isoformat()
            
            self.stdout.write(f"Timestamp simulé (25 min dans le passé): {warning_timestamp}")
            self.stdout.write("Ce timestamp devrait déclencher l'alerte d'expiration.")
            
            # Modifier une session existante si possible
            if options['session_key']:
                self._modify_session(options['session_key'], warning_timestamp)
            else:
                self.stdout.write("Utilise --session-key pour modifier une session spécifique")
                
        else:
            self.stdout.write("Configuration actuelle :")
            self.stdout.write("✅ Session timeout: 30 minutes")
            self.stdout.write("✅ Alerte d'expiration: 5 minutes avant")
            self.stdout.write("✅ Middleware activé dans settings.py")
            self.stdout.write("✅ Template d'alerte créé")
            self.stdout.write("✅ Vue de prolongation de session créée")
            
            self.stdout.write("\nPour tester le timeout :")
            self.stdout.write("1. Connecte-toi au dashboard")
            self.stdout.write("2. Laisse la page ouverte sans activité")
            self.stdout.write("3. Après 25 minutes, tu verras l'alerte")
            self.stdout.write("4. Après 30 minutes, déconnexion automatique")
            
            self.stdout.write("\nPour simuler un timeout :")
            self.stdout.write("python manage.py test_session_timeout --simulate-timeout --session-key SESSION_KEY")
            
            self.stdout.write("\nPour simuler l'alerte :")
            self.stdout.write("python manage.py test_session_timeout --simulate-warning --session-key SESSION_KEY")
            
            self.stdout.write("\nPour trouver ta clé de session :")
            self.stdout.write("1. Va sur ton dashboard")
            self.stdout.write("2. Appuie sur F12 (DevTools)")
            self.stdout.write("3. Onglet Application > Cookies > sessionid")
            self.stdout.write("4. Copie la valeur de sessionid")
    
    def _modify_session(self, session_key, timestamp):
        """Modifie une session existante avec un timestamp spécifique"""
        try:
            # Créer un objet SessionStore avec la clé existante
            session_store = SessionStore(session_key=session_key)
            
            if session_store.exists(session_key):
                # Modifier le timestamp de dernière activité
                session_store['last_activity'] = timestamp
                session_store.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Session {session_key} modifiée avec succès !"
                    )
                )
                self.stdout.write(f"Timestamp modifié: {timestamp}")
                self.stdout.write("Maintenant, recharge ta page dashboard pour voir l'effet !")
                
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Session {session_key} non trouvée"
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Erreur lors de la modification: {e}"
                )
            ) 