from .models import Logo

def logo_actif(request):
    logo = Logo.objects.filter(actif=True).first()
    return {'logo_actif': logo}
