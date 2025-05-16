from django.db import models

# Create your modelsfrom django.db import models

class Commercial(models.Model):
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
    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Rendezvous(models.Model):
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    date_rdv = models.DateField()
    heure_rdv = models.TimeField()
    objet = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RDV avec {self.client} le {self.date_rdv} à {self.heure_rdv}"