from django.conf import settings
from django.core.mail import send_mail

from .models import MembreRoles
from django.http import HttpResponseForbidden
from functools import wraps

def est_tresorier(user):
    if not hasattr(user, 'membre'):
        return False
    return MembreRoles.objects.filter(
        membre=user.membre,
        role__nom__iexact="Trésorier",
        est_actif=True
    ).exists()


def tresorier_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Vous devez être connecté.")
        if not est_tresorier(request.user):
            return HttpResponseForbidden("Accès réservé aux trésoriers.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def envoyer_mail(destinataires, sujet, contenu):
    send_mail(
        sujet,
        contenu,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=destinataires,
        fail_silently=False,
    )
