from django import template
from gestion.utils import est_tresorier

register = template.Library()

@register.filter
def is_tresorier(user):
    return est_tresorier(user)