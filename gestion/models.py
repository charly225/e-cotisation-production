import re
from django.core.exceptions import ValidationError
from datetime import date
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from ckeditor.fields import RichTextField
from django.db.models import Sum

def generate_year_choices(start=2020, end=None):
    from datetime import datetime
    end = end or datetime.now().year + 5
    return [
        (f"{y}-{y+1}", f"{y}-{y+1}")
        for y in range(start, end)
    ]
class Logo(models.Model):
    nom = models.CharField(max_length=100, blank=True, help_text="Nom ou description du logo")
    image = models.ImageField(upload_to='logos/', verbose_name="Fichier logo (SVG, PNG, etc.)")
    actif = models.BooleanField(default=False, help_text="Définit si ce logo est utilisé actuellement")

    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom or f"Logo #{self.pk}"

    class Meta:
        ordering = ['-actif', '-date_ajout']

class Membre(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True)
    date_adhesion = models.DateField(auto_now_add=True)
    est_actif = models.BooleanField(default=True)
    est_decede = models.BooleanField(default=False)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Photo de profil optionnelle
    photo = models.ImageField(upload_to='membres/photos/', blank=True, null=True)

    class Meta:
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()

    def get_enfants_actifs(self):
        return self.enfants.filter(est_actif=True)


class Enfant(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True)
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    sexe = models.CharField(
        max_length=1,
        choices=SEXE_CHOICES,
        default='M',
        help_text="Sexe de l'enfant"
    )
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=100, blank=True)
    membre_parent = models.ForeignKey(
        Membre,
        on_delete=models.SET_NULL,
        null=True,
        related_name="enfants"
    )
    est_actif = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='enfants/photos/', blank=True, null=True)

    class Meta:
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )

    def clean(self):
        if self.date_naissance > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")

class Cotisation(models.Model):
    libelle = models.CharField(max_length=100, blank=True, null=True)
    annee = models.CharField(max_length=9)  # Exemple: "2023-2024"
    objectif_global = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Objectif total à atteindre pour cette cotisation"
    )
    est_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-annee']

    def __str__(self):
        return self.libelle

    @property
    def montant_collecte(self):
        """Retourne le montant total collecté pour cette cotisation"""
        return sum(p.montant for p in self.payement_set.filter(validee=True))

    @property
    def taux_realisation(self):
        """Retourne le taux de réalisation en pourcentage"""
        if self.objectif_global > 0:
            taux = (self.montant_collecte / self.objectif_global) * 100
            return min(taux, 100) #Empêche de dépasser les 100%
        return 0

    def mettre_a_jour_objectif(self):
        total = self.objectifniveaucotisation_set.aggregate(somme=Sum('montant'))['somme'] or 0
        self.objectif_global = total
        self.save(update_fields=['objectif_global'])

    def clean(self):
        import re
        if not re.match(r'^\d{4}-\d{4}$', self.annee):
            raise ValidationError("L'année doit être au format '2023-2024'.")

class NiveauScolaire(models.Model):
    nom = models.CharField(max_length=50)  # Exemple: "6e", "Terminale"
    ordre = models.IntegerField(default=0, help_text="Ordre d'affichage")

    class Meta:
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom

class ObjectifNiveauCotisation(models.Model):
    niveau = models.ForeignKey(NiveauScolaire, on_delete=models.CASCADE)
    cotisation = models.ForeignKey(Cotisation, on_delete=models.CASCADE)
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))]
    )

    class Meta:
        unique_together = ('niveau', 'cotisation')

    def __str__(self):
        return f"{self.niveau.nom} - {self.cotisation.libelle} ({self.montant} FCFA)"

class ScolariteEnfant(models.Model):
    enfant = models.ForeignKey('Enfant', on_delete=models.CASCADE)
    niveau = models.ForeignKey('NiveauScolaire', on_delete=models.CASCADE)
    annee = models.CharField(
        max_length=9,
        help_text="Format obligatoire : 2023-2024"
    )
    etablissement = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('enfant', 'annee')
        ordering = ['-annee', 'niveau__ordre']

    def __str__(self):
        return f"{self.enfant} en {self.niveau.nom} ({self.annee})"

    def clean(self):
        # Vérifie le format avec un pattern stricte
        if not re.match(r"^\d{4}-\d{4}$", self.annee):
            raise ValidationError("Le format de l'année doit être : 2023-2024")

        # Découper l'année en deux parties
        debut, fin = map(int, self.annee.split("-"))

        # Vérifie que la fin est exactement l'année suivante
        if fin != debut + 1:
            raise ValidationError("L'année de fin doit être exactement un an après l'année de début.")

        # Vérifie l'unicité (hors mise à jour du même enregistrement)
        if ScolariteEnfant.objects.filter(
            enfant=self.enfant,
            annee=self.annee
        ).exclude(id=self.id).exists():
            raise ValidationError("L'enfant est déjà inscrit pour cette année scolaire.")

class MoyenPaiement(models.Model):
    code = models.CharField(max_length=30, unique=True)
    libelle = models.CharField(max_length=100)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class Payement(models.Model):
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE)
    cotisation = models.ForeignKey(Cotisation, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_paiement = models.DateField(auto_now_add=True)
    moyen_paiement = models.ForeignKey(
        MoyenPaiement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    validee = models.BooleanField(default=False)
    validee_par = models.ForeignKey(
        Membre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements_valides'
    )

    class Meta:
        ordering = ['-date_paiement']

    def __str__(self):
        return f"{self.membre.nom_complet} - {self.montant} FCFA ({self.cotisation.libelle})"



class ParametrageCotisation(models.Model):
    cotisation = models.OneToOneField(Cotisation, on_delete=models.CASCADE)
    est_cotisation_libre = models.BooleanField(
        default=True,
        help_text="Si coché, les membres peuvent choisir le montant à verser"
    )
    montant_fixe = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Si la cotisation est fixe, indiquez le montant que chaque membre doit verser."
    )
    montant_minimum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Montant minimum pour les cotisations libres"
    )
    accepter_paiement_partiel = models.BooleanField(
        default=True,
        help_text="Autoriser les paiements partiels"
    )

    def __str__(self):
        if self.est_cotisation_libre:
            liberte = "libre"
            if self.montant_minimum:
                liberte += f" (min: {self.montant_minimum} FCFA)"
        else:
            liberte = f"fixe ({self.montant_fixe} FCFA)"
        return f"Cotisation {self.cotisation.libelle} - {liberte}"


class Role(models.Model):
    nom = models.CharField(max_length=50)  # Exemple: Trésorier, Président
    description = models.TextField(blank=True)
    permissions = models.TextField(
        blank=True,
        help_text="Permissions spéciales pour ce rôle (JSON)"
    )

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class MembreRoles(models.Model):
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    est_actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ('membre', 'role')
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.membre.nom} - {self.role.nom}"


# Nouveaux modèles pour améliorer le système

class Notification(models.Model):
    TYPE_CHOICES = [
        ('RAPPEL', 'Rappel de paiement'),
        ('VALIDATION', 'Validation de paiement'),
        ('ANNONCE', 'Annonce générale'),
    ]

    titre = models.CharField(max_length=200)
    message = models.TextField()
    type_notification = models.CharField(max_length=20, choices=TYPE_CHOICES)
    destinataire = models.ForeignKey(Membre, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    est_lue = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.titre} - {self.destinataire.nom}"


class RappelPaiement(models.Model):
    cotisation = models.ForeignKey(Cotisation, on_delete=models.CASCADE)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE)
    date_rappel = models.DateTimeField(auto_now_add=True)
    montant_du = models.DecimalField(max_digits=12, decimal_places=2)
    message_personnalise = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_rappel']

    def __str__(self):
        return f"Rappel - {self.membre.nom} - {self.cotisation.libelle}"

class MessageAccueil(models.Model):
    titre = models.CharField(max_length=200, help_text="Titre principal en haut de la page d'accueil")
    sous_titre = RichTextField()
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Message d'accueil"
        verbose_name_plural = "Messages d'accueil"

    def __str__(self):
        return self.titre

class Temoignage(models.Model):
    nom = models.CharField(max_length=100)
    lien_avec_enfant = models.CharField(
        max_length=100,
        help_text="Ex : Père, Mère, Grand frère, Tuteur...",
        default="Anonyme",
        blank=True,
    )
    message = models.TextField()
    nombre_etoiles = models.PositiveSmallIntegerField(default=5)
    est_visible = models.BooleanField(default=False)
    date_creation = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.nom} ({self.lien_avec_enfant})"


class AppelAction(models.Model):
    titre = models.CharField(max_length=150)
    texte = RichTextField()
    texte_bouton = models.CharField(max_length=100, default="Commencer maintenant")
    lien_bouton = models.URLField(blank=True, null=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Appel à l'action"
        verbose_name_plural = "Appels à l'action"

    def __str__(self):
        return self.titre

class SectionMission(models.Model):
    titre = models.CharField(max_length=200, default="Notre mission de solidarité")
    description = models.TextField()
    est_visible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Section - Mission"
        verbose_name_plural = "Section - Mission"

    def __str__(self):
        return self.titre

class PointMission(models.Model):
    section = models.ForeignKey(SectionMission, on_delete=models.CASCADE, related_name="points")
    texte = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Point clé de mission"
        verbose_name_plural = "Points clés de mission"

    def __str__(self):
        return self.texte
