from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from functools import wraps

def membre_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'membre'):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Accès réservé aux membres de l'association.")
    return _wrapped_view
