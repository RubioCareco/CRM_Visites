from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User

class Command(BaseCommand):
    help = 'Crée le groupe "responsable" et y ajoute des utilisateurs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--emails',
            nargs='+',
            type=str,
            help='Liste des emails des responsables à ajouter au groupe'
        )

    def handle(self, *args, **options):
        # Créer le groupe "responsable" s'il n'existe pas
        groupe_responsable, created = Group.objects.get_or_create(name='responsable')
        
        if created:
            self.stdout.write('✅ Groupe "responsable" créé')
        else:
            self.stdout.write('ℹ️ Groupe "responsable" existe déjà')
        
        # Ajouter des utilisateurs au groupe si spécifiés
        if options['emails']:
            for email in options['emails']:
                try:
                    user = User.objects.get(email=email)
                    user.groups.add(groupe_responsable)
                    self.stdout.write(f'✅ Utilisateur {user.username} ajouté au groupe responsable')
                except User.DoesNotExist:
                    self.stdout.write(f'❌ Utilisateur avec l\'email {email} non trouvé')
        
        # Afficher tous les membres du groupe
        membres = groupe_responsable.user_set.all()
        if membres:
            self.stdout.write('\n📋 Membres du groupe "responsable" :')
            for membre in membres:
                self.stdout.write(f'  - {membre.username} ({membre.email})')
        else:
            self.stdout.write('\n⚠️ Aucun membre dans le groupe "responsable"')
            self.stdout.write('💡 Utilise --emails pour ajouter des responsables')
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Configuration terminée !')
        ) 