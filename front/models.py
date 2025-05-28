from django.db import models
from django.contrib.auth.models import User

class Commercial(models.Model):
    commercial = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=15)
    password = models.CharField(max_length=255)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    entreprise = models.CharField(max_length=150, blank=True, null=True)
    siret = models.CharField(max_length=14, unique=True, blank=True, null=True)
    adresse = models.CharField(max_length=250, blank=True, null=True)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    telephone = models.CharField(max_length=15, blank=True, null=True)
    commercial = models.ForeignKey('Commercial', on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Rendezvous(models.Model):
    client = models.ForeignKey('ImportClientCorrected', on_delete=models.SET_NULL, null=True, blank=True)
    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    date_rdv = models.DateField()
    heure_rdv = models.TimeField()
    objet = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_statut = models.DateTimeField(null=True, blank=True)  # Date du dernier changement de statut

    def __str__(self):
        return f"RDV avec {self.client} le {self.date_rdv} à {self.heure_rdv}"

# Historique des commentaires sur les rendez-vous
class CommentaireRdv(models.Model):
    rdv = models.ForeignKey(Rendezvous, on_delete=models.CASCADE, related_name='commentaires')
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    texte = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.auteur} - {self.date_creation.strftime('%d/%m/%Y %H:%M')} : {self.texte[:30]}"

class ImportClientCorrected(models.Model):
    civilite = models.CharField(max_length=50, blank=True, null=True)
    rs_nom = models.CharField(max_length=64, blank=True, null=True)
    prénom = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.CharField(max_length=60, blank=True, null=True)
    code_postal = models.CharField(max_length=50, blank=True, null=True)
    ville = models.CharField(max_length=60, blank=True, null=True)
    commercial = models.CharField(max_length=50, blank=True, null=True)
    telephone = models.CharField(max_length=15, blank=True, null=True)
    e_mail = models.CharField(max_length=60, blank=True, null=True)
    statut= models.CharField(max_length=50, blank=True, null=True)

    # ... autres champs si besoin

    class Meta:
        db_table = 'import_clients_corrected'
        managed = False
