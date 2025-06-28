from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from gestion.models import ObjectifNiveauCotisation, ScolariteEnfant

@receiver([post_save, post_delete], sender=ObjectifNiveauCotisation)
def maj_objectif_global(sender, instance, **kwargs):
    instance.cotisation.mettre_a_jour_objectif()

@receiver([post_save, post_delete], sender=ScolariteEnfant)
def maj_objectif_niveau_cotisation(sender, instance, **kwargs):
    # Met à jour le montant de l'ObjectifNiveauCotisation correspondant
    from decimal import Decimal
    obj = ObjectifNiveauCotisation.objects.filter(
        niveau=instance.niveau,
        cotisation__annee=instance.annee
    ).first()
    if obj:
        # recalcul automatique via save()
        obj.save()
