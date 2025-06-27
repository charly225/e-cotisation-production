from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from gestion.models import ObjectifNiveauCotisation

@receiver([post_save, post_delete], sender=ObjectifNiveauCotisation)
def maj_objectif_global(sender, instance, **kwargs):
    instance.cotisation.mettre_a_jour_objectif()
