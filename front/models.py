from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import uuid
from .siret_utils import validate_siret


class Commercial(models.Model):
    commercial = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=15)
    password = models.CharField(max_length=255)
    date_creation = models.DateTimeField(auto_now_add=True)
    site_rattachement = models.CharField(max_length=100, blank=True, null=True)
    # Champs pour la géolocalisation du point de départ
    latitude_depart = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude_depart = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    adresse_depart = models.CharField(max_length=255, blank=True, null=True)

    ROLE_CHOICES = [
        ('commercial', 'Commercial'),
        ('responsable', 'Responsable'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='commercial')
    is_absent = models.BooleanField(default=False)  # Nouveau champ pour le switch absence

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    class Meta:
        managed = True


class Rendezvous(models.Model):
    STATUT_CHOICES = [
        ('a_venir', 'À venir'),
        ('valide', 'Validé'),
        ('annule', 'Annulé'),
        ('gele', 'Gelé'),  # Nouveau statut pour les RDV gelés
    ]
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    client = models.ForeignKey('FrontClient', on_delete=models.SET_NULL, null=True, blank=True)
    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    date_rdv = models.DateField()
    heure_rdv = models.TimeField()
    objet = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_statut = models.DateTimeField(null=True, blank=True)  # Date du dernier changement de statut
    statut_rdv = models.CharField(max_length=16, choices=STATUT_CHOICES, default='a_venir')
    rs_nom = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f"RDV avec {self.client} le {self.date_rdv} à {self.heure_rdv}"

    class Meta:
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["commercial", "client", "date_rdv", "heure_rdv"],
                name="uniq_rdv_commercial_client_datetime",
        )
    ]


# Historique des commentaires sur les rendez-vous
class CommentaireRdv(models.Model):
    rdv = models.ForeignKey(Rendezvous, on_delete=models.CASCADE, related_name='commentaires')
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    texte = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    rs_nom = models.CharField(max_length=128, blank=True, null=True)
    # 👇 Nouveau champ pour les commentaires épinglés
    is_pinned = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.auteur} - {self.date_creation.strftime('%d/%m/%Y %H:%M')} : {self.texte[:30]}"

    class Meta:
        managed = True


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
    statut = models.CharField(max_length=50, blank=True, null=True)
    code_comptable = models.CharField(max_length=64, blank=True, null=True)
    e_mail_comptabilité = models.CharField(max_length=60, blank=True, null=True)
    en_compte = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'import_clients_corrected'
        managed = False  # Table historique: on ne la gère plus via Django


class SatisfactionB2B(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pdf_base64 = models.TextField(blank=True, null=True)
    date_soumission = models.DateTimeField(auto_now_add=True)
    rs_nom = models.CharField(max_length=255, default="Inconnu")  # Obligatoire, valeur par défaut pour migration
    commercial = models.ForeignKey('Commercial', on_delete=models.SET_NULL, null=True, blank=True)
    rdv = models.ForeignKey('Rendezvous', on_delete=models.SET_NULL, null=True, blank=True)

    # Champs pour chaque question du formulaire
    satisfaction_qualite_pieces = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    note_qualite_pieces = models.PositiveSmallIntegerField(blank=True, null=True)
    probleme_qualite_piece = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    type_probleme_qualite_piece = models.TextField(blank=True, null=True)
    satisfaction_delai_livraison = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    delai_livraison_moyen = models.CharField(max_length=20, blank=True, null=True)
    delai_livraison_ideal = models.CharField(max_length=20, blank=True, null=True)
    delai_livraison_ideal_autre = models.TextField(blank=True, null=True)
    recours_sav = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    note_sav = models.PositiveSmallIntegerField(blank=True, null=True)
    piece_non_dispo = models.TextField(blank=True, null=True)
    satisfaction_experience_rubio = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    personnel_joignable = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    note_accueil = models.PositiveSmallIntegerField(blank=True, null=True)
    commande_simple = models.CharField(max_length=5, choices=[('oui', 'Oui'), ('non', 'Non')], blank=True, null=True)
    moyen_commande = models.CharField(max_length=20, blank=True, null=True)
    moyen_commande_autre = models.TextField(blank=True, null=True)
    suggestion = models.TextField(blank=True, null=True)
    motivation_commande = models.TextField(blank=True, null=True)
    note_recommandation = models.PositiveSmallIntegerField(blank=True, null=True)

    # Nouvelle colonne pour la moyenne
    moyenne = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    # Nouvelle colonne pour le score hybride (numérique + textuel)
    score_hybride = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Calcul de la moyenne des notes disponibles
        notes = []
        if self.note_qualite_pieces is not None:
            try:
                notes.append(int(self.note_qualite_pieces))
            except (ValueError, TypeError):
                pass
        if self.note_sav is not None:
            try:
                notes.append(int(self.note_sav))
            except (ValueError, TypeError):
                pass
        if self.note_accueil is not None:
            try:
                notes.append(int(self.note_accueil))
            except (ValueError, TypeError):
                pass
        if self.note_recommandation is not None:
            try:
                notes.append(int(self.note_recommandation))
            except (ValueError, TypeError):
                pass

        if notes:
            self.moyenne = sum(notes) / len(notes)
        else:
            self.moyenne = None

        # Calcul du score hybride (numérique + analyse textuelle)
        try:
            from .utils import calculate_comprehensive_satisfaction_score
            self.score_hybride = calculate_comprehensive_satisfaction_score(self)
        except Exception:
            # En cas d'erreur, on garde le score numérique uniquement
            if self.moyenne:
                # La moyenne peut contenir des notes sur 5 et sur 10, donc on ne multiplie pas par 2
                # car cela pourrait donner des valeurs supérieures à 10
                self.score_hybride = min(self.moyenne, 10.0)  # Limiter à 10 maximum
            else:
                self.score_hybride = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Satisfaction B2B #{self.id} - {self.rs_nom} - {self.date_soumission.strftime('%d/%m/%Y')}"


class ActivityLog(models.Model):
    ACTION_TYPES = [
        ('RDV_AJOUTE', 'RDV Ajouté'),
        ('RDV_VALIDE', 'RDV Validé'),
        ('RDV_ANNULE', 'RDV Annulé'),
        ('CLIENT_AJOUTE', 'Client Ajouté'),
        ('ABSENCE_ON', 'Commercial absent'),
        ('ABSENCE_OFF', 'Commercial présent'),
    ]

    commercial = models.ForeignKey(Commercial, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.commercial} - {self.action_type} at {self.timestamp}'

    class Meta:
        ordering = ['-timestamp']


class FrontClient(models.Model):
    nom = models.CharField(max_length=100, blank=True, null=True)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    civilite = models.CharField(max_length=50, blank=True, null=True)
    rs_nom = models.CharField(max_length=64, blank=True, null=True)
    telephone = models.CharField(max_length=100, blank=True, null=True)
    statut = models.CharField(max_length=50, blank=True, null=True)
    en_compte = models.BooleanField(default=False)
    actif = models.BooleanField(default=False)
    code_comptable = models.CharField(max_length=64, blank=True, null=True)
    email = models.CharField(max_length=254, blank=True, null=True)
    email_comptabilite = models.CharField(max_length=254, blank=True, null=True)
    siret = models.CharField(max_length=14, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    commercial_id = models.BigIntegerField(null=True, blank=True)
    commentaires = models.TextField(null=True, blank=True)
    commercial = models.CharField(max_length=100, blank=True, null=True)
    classement_client = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Type de client (A, B, C) pour déterminer l'objectif annuel de visites",
    )

    def clean(self):
        super().clean()
        is_valid, cleaned, error = validate_siret(self.siret)
        if not is_valid:
            raise ValidationError({"siret": error})
        self.siret = cleaned or None

    class Meta:
        db_table = 'front_client'
        managed = True


class Adresse(models.Model):
    client = models.ForeignKey(FrontClient, on_delete=models.CASCADE, related_name='adresses')
    adresse = models.CharField(max_length=250, blank=True, null=True)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    ville = models.CharField(max_length=60, blank=True, null=True)
    # Champs pour la géolocalisation
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    geocode_date = models.DateTimeField(blank=True, null=True)  # Date du dernier géocodage

    class Meta:
        db_table = 'adresse'

    def __str__(self):
        return f"{self.adresse}, {self.code_postal} {self.ville}"


class ClientVisitStats(models.Model):
    """Statistiques annuelles de visites par client et commercial"""
    client = models.ForeignKey('FrontClient', on_delete=models.CASCADE, related_name='stats_visites')
    commercial = models.ForeignKey(Commercial, on_delete=models.CASCADE, related_name='stats_visites')
    annee = models.IntegerField()
    visites_valides = models.IntegerField(default=0, help_text="Nombre de visites validées cette année")
    objectif = models.IntegerField(help_text="Objectif annuel de visites (A=10, B=5, C=1, défaut=1)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client', 'commercial', 'annee']
        verbose_name = "Statistique de visite client"
        verbose_name_plural = "Statistiques de visites clients"
        indexes = [
            models.Index(fields=['client', 'annee']),
            models.Index(fields=['commercial', 'annee']),
        ]

    def __str__(self):
        return f"{self.client} - {self.commercial} - {self.annee} ({self.visites_valides}/{self.objectif})"

    @property
    def ratio(self):
        """Retourne le ratio sous forme 'X/Y'"""
        return f"{self.visites_valides}/{self.objectif}"
