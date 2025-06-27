from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Membre, Enfant, Cotisation, NiveauScolaire, ObjectifNiveauCotisation,
    ScolariteEnfant, MoyenPaiement, Payement,
    ParametrageCotisation, Role, MembreRoles,
    Notification, RappelPaiement, MessageAccueil, Temoignage, AppelAction, PointMission, SectionMission, Logo
)

@admin.register(Logo)
class LogoAdmin(admin.ModelAdmin):
    list_display = ['nom', 'actif', 'date_ajout']
    list_filter = ['actif']
    search_fields = ['nom']

    def save_model(self, request, obj, form, change):
        if obj.actif:
            # Désactive tous les autres logos
            Logo.objects.update(actif=False)
        super().save_model(request, obj, form, change)
class PayementAdminForm(forms.ModelForm):
    class Meta:
        model = Payement
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer pour ne garder que les membres qui sont trésoriers actifs
        tresoriers_ids = MembreRoles.objects.filter(
            role__nom__iexact='trésorier',
            est_actif=True
        ).values_list('membre_id', flat=True)

        self.fields['validee_par'].queryset = Membre.objects.filter(id__in=tresoriers_ids)

@admin.register(Payement)
class PayementAdmin(admin.ModelAdmin):
    form = PayementAdminForm  # 👈 formulaire personnalisé
    list_display = ('membre', 'cotisation', 'montant', 'validee', 'validee_par', 'date_paiement')
    list_filter = ('validee', 'cotisation', 'moyen_paiement')
    search_fields = ('membre__nom', 'cotisation__libelle')


# --- MessageAccueil ---
@admin.register(MessageAccueil)
class MessageAccueilAdmin(admin.ModelAdmin):
    list_display = ('titre', 'actif')

# --- Temoignage ---
@admin.register(Temoignage)
class TemoignageAdmin(admin.ModelAdmin):
    list_display = ('nom', 'lien_avec_enfant')

# --- AppelAction ---
@admin.register(AppelAction)
class AppelActionAdmin(admin.ModelAdmin):
    list_display = ('titre', 'actif')
    list_filter = ('actif',)

# --- Membre ---
@admin.register(Membre)
class MembreAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'est_actif', 'est_decede')
    list_filter = ('est_actif', 'est_decede', 'date_adhesion')
    search_fields = ('nom', 'prenom', 'email')

# --- Enfant ---
@admin.register(Enfant)
class EnfantAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'membre_parent', 'date_naissance', 'est_actif')
    list_filter = ('est_actif', 'sexe')
    search_fields = ('nom', 'prenom', 'membre_parent__nom')

# --- Cotisation ---
@admin.register(Cotisation)
class CotisationAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'annee', 'objectif_global', 'montant_collecte', 'taux_realisation', 'est_active')
    list_filter = ('annee', 'est_active')
    search_fields = ('libelle', 'annee')
    readonly_fields = ('objectif_global',)

# --- Niveau scolaire ---
@admin.register(NiveauScolaire)
class NiveauScolaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre')
    ordering = ('ordre',)
    search_fields = ('nom',)

# --- Objectif par niveau ---
@admin.register(ObjectifNiveauCotisation)
class ObjectifNiveauCotisationAdmin(admin.ModelAdmin):
    list_display = ('niveau', 'cotisation', 'montant')
    list_filter = ('cotisation', 'niveau')
    search_fields = ('cotisation__libelle',)

# --- Scolarité enfant ---
@admin.register(ScolariteEnfant)
class ScolariteEnfantAdmin(admin.ModelAdmin):
    list_display = ('enfant', 'niveau', 'annee', 'etablissement')
    list_filter = ('niveau', 'annee')
    search_fields = ('enfant__nom', 'annee')

    def save_model(self, request, obj, form, change):
        if ScolariteEnfant.objects.filter(enfant=obj.enfant, niveau=obj.niveau, annee=obj.annee).exists():
            raise ValidationError("Doublon détecté pour cette scolarité.")
        super().save_model(request, obj, form, change)

# --- Moyen de paiement (simplifié) ---
@admin.register(MoyenPaiement)
class MoyenPaiementAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'code')
    search_fields = ('libelle', 'code')

# --- Paramétrage cotisation ---
@admin.register(ParametrageCotisation)
class ParametrageCotisationAdmin(admin.ModelAdmin):
    list_display = ('cotisation', 'est_cotisation_libre', 'montant_fixe', 'montant_minimum', 'accepter_paiement_partiel')

# --- Rôles ---
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')

# --- Rôles des membres ---
@admin.register(MembreRoles)
class MembreRolesAdmin(admin.ModelAdmin):
    list_display = ('membre', 'role', 'date_debut', 'est_actif')
    list_filter = ('role', 'est_actif')

# --- Notifications ---
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('titre', 'destinataire', 'type_notification', 'date_creation', 'est_lue')
    list_filter = ('type_notification', 'est_lue')

# --- Rappels de paiement ---
@admin.register(RappelPaiement)
class RappelPaiementAdmin(admin.ModelAdmin):
    list_display = ('membre', 'cotisation', 'montant_du', 'date_rappel')
    list_filter = ('cotisation',)
    search_fields = ('membre__nom',)

class PointMissionInline(admin.TabularInline):
    model = PointMission
    extra = 1

@admin.register(SectionMission)
class SectionMissionAdmin(admin.ModelAdmin):
    list_display = ("titre", "est_visible")
    inlines = [PointMissionInline]
