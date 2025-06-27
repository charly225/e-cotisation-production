from django import template
from gestion.models import MembreRoles

register = template.Library()

@register.filter
def is_tresorier(user):
    if hasattr(user, 'membre'):
        return MembreRoles.objects.filter(membre=user.membre, role__nom__iexact='trésorier', est_actif=True).exists()
    return False
