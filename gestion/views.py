from django.conf import settings
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.db.models import Sum, Max
from django.urls import reverse
from .decorators import membre_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
import logging
from .forms import TemoignagePublicForm, LoginForm, RegisterForm, PaiementForm, ProfilForm
from .models import (Membre, Enfant, Cotisation, MessageAccueil, AppelAction, Temoignage, SectionMission, MoyenPaiement, Payement, MembreRoles)
from .utils import envoyer_mail
logger = logging.getLogger(__name__)

def accueil(request):
    campagne = Cotisation.objects.filter(est_active=True).first()
    message_accueil = MessageAccueil.objects.filter(actif=True).first()
    appel_action = AppelAction.objects.filter(actif=True).first()

    # Récupération de tous les témoignages visibles pour la pagination
    temoignages_list = Temoignage.objects.filter(est_visible=True).order_by('-date_creation')

    # Configuration de la pagination (3 témoignages par page)
    paginator = Paginator(temoignages_list, 3)
    page_number = request.GET.get('page')
    temoignages_page = paginator.get_page(page_number)

    # Garder les 4 premiers pour d'autres sections si nécessaire
    temoignages_highlights = temoignages_list[:4]

    form = TemoignagePublicForm()
    cotisation_active = Cotisation.objects.filter(est_active=True).first()
    section_mission = SectionMission.objects.filter(est_visible=True).first()

    # Statistiques simples
    nombre_enfants = Enfant.objects.filter(est_actif=True).count()
    nombre_membres = Membre.objects.filter(est_actif=True).count()
    montant_collecte = campagne.montant_collecte if campagne else 0

    # Traitement du formulaire
    form = TemoignagePublicForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        temoignage = form.save(commit=False)
        temoignage.est_valide = False  # En attente de validation
        temoignage.save()

        # Si requête AJAX, retourner une réponse JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': "Merci pour votre témoignage ! Il sera affiché après validation."
            })
        return redirect(f"{reverse('accueil')}?temoignage=ok")


    # Si requête AJAX pour la pagination
    if request.GET.get('ajax'):
        # Rendre le template en string pour les témoignages
        html = render_to_string('gestion/partials/testimonials_list.html', {
            'temoignages_page': temoignages_page
        })

        # Rendre le template en string pour la pagination
        pagination_html = render_to_string('gestion/partials/pagination.html', {
            'temoignages_page': temoignages_page
        })

        return JsonResponse({
            'html': html,
            'pagination_html': pagination_html,
            'current_page': temoignages_page.number,
            'total_pages': paginator.num_pages
        })
    temoignage_submitted = request.GET.get('temoignage') == 'ok'

    context = {
        'campagne': campagne,
        'message_accueil': message_accueil,
        'appel_action': appel_action,
        'nombre_enfants': nombre_enfants,
        'nombre_membres': nombre_membres,
        'montant_collecte': montant_collecte,
        'cotisation_active': cotisation_active,
        'section_mission': section_mission,
        'temoignages': temoignages_highlights,  # Pour d'autres sections
        'temoignages_page': temoignages_page,  # Pour la section avec pagination
        'form': form,
        'temoignage_submitted': temoignage_submitted,
    }
    return render(request, 'gestion/index.html', context)

def chargement(request):
    return render(request, 'gestion/loading.html')

def auth(request):
    login_form = LoginForm(request, data=request.POST or None)
    register_form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if 'login_submit' in request.POST and login_form.is_valid():
            user = login_form.get_user()
            login(request, user)
            next_url = request.POST.get('next')
            messages.success(request, "Connexion réussie !")
            redirect_url = f"{reverse('auth')}?login_success=1"
            if next_url:
                redirect_url += f"&next={next_url}"
            return redirect(redirect_url)


        elif 'register_submit' in request.POST and register_form.is_valid():
            user = register_form.save(commit=False)
            user.set_password(register_form.cleaned_data['password'])
            user.save()
            nom_complet = register_form.cleaned_data['nom_complet']
            nom, *prenom = nom_complet.strip().split(' ', 1)
            from .models import Membre
            Membre.objects.create(
                user=user,
                nom=nom,
                prenom=prenom[0] if prenom else '',
                email=user.email
            )
            messages.success(request, "Compte créé avec succès. Vous pouvez maintenant vous connecter.")
            next_url = request.POST.get('next')
            return redirect(f"{reverse('auth')}?next={next_url}" if next_url else 'auth')
    context = {
        'login_form': login_form,
        'register_form': register_form
    }
    return render(request, 'gestion/auth.html', context)

@membre_required
def effectuer_paiement(request):

    membre = request.user.membre
    form = PaiementForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        paiement = form.save(commit=False)
        paiement.membre = membre
        cotisation = paiement.cotisation
        param = getattr(cotisation, 'parametragecotisation', None)

        if param:
            if not param.est_cotisation_libre:
                paiement.montant = param.montant_fixe
            elif param.montant_minimum and paiement.montant < param.montant_minimum:
                # form.add_error('montant', f"Le montant minimum est de {param.montant_minimum} FCFA.")
                error_msg = f"Le montant minimum est de {param.montant_minimum} FCFA."
                # Si c'est une requête AJAX, retourner JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_msg
                    }, status=400)
                form.add_error('montant', error_msg)
                return render(request, 'gestion/paiement.html', {
                    'form': form,
                    'cotisations': Cotisation.objects.filter(est_active=True),
                    'moyens': MoyenPaiement.objects.filter(est_actif=True)
                })

        paiement.save()
        tresoriers = MembreRoles.objects.filter(role__nom__iexact='trésorier', est_actif=True)
        emails_tresoriers = [t.membre.email for t in tresoriers if t.membre.email]
        if emails_tresoriers:
            contenu = f"{membre.nom_complet} vient d'effectuer un paiement de {paiement.montant} FCFA pour la cotisation « {paiement.cotisation.libelle} ». Veuillez le valider depuis votre tableau de bord."
            envoyer_mail(
                destinataires=emails_tresoriers,
                sujet="📩 Nouveau paiement en attente de validation",
                contenu=contenu
            )
        # Si c'est une requête AJAX, retourner JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Merci pour votre contribution !',
                'paiement': {
                    'montant': paiement.montant,
                    'cotisation': paiement.cotisation.libelle,
                    'moyen_paiement': paiement.moyen_paiement.libelle
                }
            })
        
        messages.success(request, "Merci pour votre contribution !")
        return redirect('accueil')
     # Si c'est une requête AJAX avec des erreurs de formulaire
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)

    objectif_depasse = False
    cotisation_active = Cotisation.objects.filter(est_active=True).first()
    if cotisation_active and cotisation_active.montant_collecte >= cotisation_active.objectif_global:
        objectif_depasse = True
    return render(request, 'gestion/paiement.html', {
        'form': form,
        'cotisations': Cotisation.objects.filter(est_active=True),
        'moyens': MoyenPaiement.objects.filter(est_actif=True),
        'objectif_depasse': objectif_depasse
    })

    membre = request.user.membre
    form = PaiementForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        paiement = form.save(commit=False)
        paiement.membre = membre
        cotisation = paiement.cotisation
        param = getattr(cotisation, 'parametragecotisation', None)

        if param:
            if not param.est_cotisation_libre:
                paiement.montant = param.montant_fixe
            elif param.montant_minimum and paiement.montant < param.montant_minimum:
                form.add_error('montant', f"Le montant minimum est de {param.montant_minimum} FCFA.")
                return render(request, 'gestion/paiement.html', {
                    'form': form,
                    'cotisations': Cotisation.objects.filter(est_active=True),
                    'moyens': MoyenPaiement.objects.filter(est_actif=True)
                })

        paiement.save()
        tresoriers = MembreRoles.objects.filter(role__nom__iexact='trésorier', est_actif=True)
        emails_tresoriers = [t.membre.email for t in tresoriers if t.membre.email]
        if emails_tresoriers:
            contenu = f"{membre.nom_complet} vient d'effectuer un paiement de {paiement.montant} FCFA pour la cotisation « {paiement.cotisation.libelle} ». Veuillez le valider depuis votre tableau de bord."
            envoyer_mail(
                destinataires=emails_tresoriers,
                sujet="📩 Nouveau paiement en attente de validation",
                contenu=contenu
            )
        messages.success(request, "Merci pour votre contribution !")
        return redirect('accueil')

    objectif_depasse = False
    cotisation_active = Cotisation.objects.filter(est_active=True).first()
    if cotisation_active and cotisation_active.montant_collecte >= cotisation_active.objectif_global:
        objectif_depasse = True
    return render(request, 'gestion/paiement.html', {
        'form': form,
        'cotisations': Cotisation.objects.filter(est_active=True),
        'moyens': MoyenPaiement.objects.filter(est_actif=True),
        'objectif_depasse': objectif_depasse
    })

def get_parametrage_cotisation(request, cotisation_id):
    try:
        cotisation = Cotisation.objects.get(pk=cotisation_id)
        param = getattr(cotisation, 'parametragecotisation', None)
        if not param:
            return JsonResponse({'error': 'Non paramétrée'}, status=404)

        return JsonResponse({
            'est_cotisation_libre': param.est_cotisation_libre,
            'montant_fixe': float(param.montant_fixe or 0),
            'montant_minimum': float(param.montant_minimum or 0),
        })

    except Cotisation.DoesNotExist:
        return JsonResponse({'error': 'Introuvable'}, status=404)

@login_required
def dashboard(request):
    membre = request.user.membre
    is_tresorier = MembreRoles.objects.filter(
        membre=membre,
        role__nom__iexact='trésorier',
        est_actif=True
    ).exists()

    context = {
        'is_tresorier': is_tresorier,
    }

    return render(request, 'gestion/dashboard_new.html', context)

@login_required
def historique_paiements(request):
    if request.GET.get("ajax") == "1":
        try:
            paiements = Payement.objects.filter(
                membre=request.user.membre,
                validee=True
            ).select_related(
                'cotisation',
                'moyen_paiement',
                'validee_par'
            ).order_by('-date_paiement')

            return render(request, "gestion/partials/historique_paiements.html", {
                'paiements': paiements
            })

        except Exception as e:
            logger.error(f"Erreur historique_paiements: {str(e)}", exc_info=True)
            return HttpResponse(
                "<div class='p-4 text-red-500'>Erreur lors du chargement. Contactez l'administrateur.</div>",
                status=500
            )
    return redirect('dashboard')

@login_required
def campagne_courante(request):
    if request.GET.get("ajax") == "1":
        cotisation_active = Cotisation.objects.filter(est_active=True).first()
        html = render_to_string("gestion/partials/campagne_courante.html", {
            'cotisation_active': cotisation_active
        })
        return HttpResponse(html)

@login_required
def modifier_profil(request):
    membre = request.user.membre
    profil_form = ProfilForm(request.POST or None, instance=membre)
    password_form = PasswordChangeForm(request.user, request.POST or None)

    if request.method == 'POST':
        if 'profil_submit' in request.POST:
            if profil_form.is_valid():
                profil_form.save()
                messages.success(request, "Profil mis à jour avec succès.")
            else:
                messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")

        elif 'password_submit' in request.POST:
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Reste connecté après modif
                messages.success(request, "Mot de passe modifié avec succès.")
            else:
                for error in password_form.errors.values():
                    messages.error(request, error)
            return redirect('modifier_profil')

    context = {
        'profil_form': profil_form,
        'password_form': password_form,
    }
    return render(request, 'gestion/profil.html', context)

@login_required
def paiements_a_valider(request):
    if request.GET.get("ajax") == "1":
        paiements = Payement.objects.filter(validee=False).select_related('cotisation', 'moyen_paiement', 'membre').order_by('-date_paiement')
        html = render_to_string("gestion/partials/paiements_a_valider.html", {'paiements': paiements})
        return JsonResponse({'html': html})
    return redirect('dashboard')

@login_required
def valider_paiement(request, pk):
    if request.method == "POST":
        paiement = get_object_or_404(Payement, pk=pk)
        paiement.validee = True
        paiement.validee_par = request.user.membre
        paiement.save()
        if paiement.membre.email:
            contenu = (
                f"Bonjour {paiement.membre.nom_complet},\n\n"
                f"Votre paiement de {paiement.montant} FCFA pour la cotisation « {paiement.cotisation.libelle} » "
                "a été validé avec succès.\n\n"
                "Merci pour votre contribution 🙏"
            )
            envoyer_mail(
                destinataires=[paiement.membre.email],
                sujet="✅ Paiement validé",
                contenu=contenu
            )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"status": "ok", "message": "Paiement validé avec succès."})
        else:
            messages.success(request, "Paiement validé avec succès.")
            return redirect('dashboard')
    else:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"status": "error", "message": "Méthode non autorisée."}, status=400)
        else:
            messages.error(request, "Requête invalide.")
            return redirect('dashboard')


@login_required
def valider_tous_les_paiements(request):
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        try:
            # Récupérer le membre qui valide
            membre_validateur = request.user.membre
            
            # Récupérer tous les paiements non validés
            paiements = Payement.objects.filter(validee=False)
            nb = paiements.count()
            
            if nb > 0:
                # Valider tous les paiements un par un pour bien renseigner validee_par
                for paiement in paiements:
                    paiement.validee = True
                    paiement.validee_par = membre_validateur
                    paiement.save()
                
                # Envoyer des emails de notification aux membres
                for paiement in Payement.objects.filter(validee=True, validee_par=membre_validateur).order_by('-date_paiement')[:nb]:
                    if paiement.membre.email:
                        contenu = (
                            f"Bonjour {paiement.membre.nom_complet},\n\n"
                            f"Votre paiement de {paiement.montant} FCFA pour la cotisation « {paiement.cotisation.libelle} » "
                            "a été validé avec succès.\n\n"
                            "Merci pour votre contribution 🙏"
                        )
                        envoyer_mail(
                            destinataires=[paiement.membre.email],
                            sujet="✅ Paiement validé",
                            contenu=contenu
                        )
                
                return JsonResponse({'message': f'{nb} paiement(s) validé(s) avec succès.'})
            else:
                return JsonResponse({'message': 'Aucun paiement en attente de validation.'})
                
        except Exception as e:
            logger.error(f"Erreur lors de la validation en masse: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Erreur lors de la validation en masse'}, status=500)
    
    return JsonResponse({'error': 'Requête invalide.'}, status=400)

@login_required
def paiements_valides_par_moi(request):
    if request.GET.get("ajax") == "1":
        # Récupère le membre lié à l'utilisateur
        membre = request.user.membre
        paiements = Payement.objects.filter(validee=True, validee_par=membre)
        html = render_to_string("gestion/partials/paiements_valides_par_moi.html", {'paiements': paiements})
        return JsonResponse({'html': html})
    return redirect('dashboard')

@login_required
def statut_cotisation(request, cotisation_id):
    try:
        cotisation = Cotisation.objects.get(pk=cotisation_id)
        collecte = cotisation.montant_collecte
        objectif = cotisation.objectif_global
        depasse = collecte >= objectif

        return JsonResponse({
            'objectif': float(objectif),
            'collecte': float(collecte),
            'objectif_depasse': depasse
        })
    except Cotisation.DoesNotExist:
        return JsonResponse({'error': 'Introuvable'}, status=404)

@login_required
def dashboard_stats(request):
    """Vue pour récupérer les statistiques du dashboard en AJAX"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            membre = request.user.membre
            is_tresorier = MembreRoles.objects.filter(
                membre=membre,
                role__nom__iexact='trésorier',
                est_actif=True
            ).exists()

            cotisation_active = Cotisation.objects.filter(est_active=True).first()
            a_contribue = False

            if cotisation_active:
                a_contribue = Payement.objects.filter(
                    membre=request.user.membre,
                    cotisation=cotisation_active,
                    validee=True
                ).exists()

            # Total collecté (global ou personnel) - TOUTES LES CAMPAGNES
            if is_tresorier:
                total_collecte_toutes_campagnes = Payement.objects.filter(validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
                mes_contributions_toutes_campagnes = Payement.objects.filter(membre=membre, validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
            else:
                total_collecte_toutes_campagnes = Payement.objects.filter(membre=membre, validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
                mes_contributions_toutes_campagnes = total_collecte_toutes_campagnes

            # Données de la campagne active uniquement
            total_collecte_campagne_active = 0
            mes_contributions_campagne_active = 0
            if cotisation_active:
                if is_tresorier:
                    total_collecte_campagne_active = Payement.objects.filter(
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                    mes_contributions_campagne_active = Payement.objects.filter(
                        membre=membre,
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                else:
                    total_collecte_campagne_active = Payement.objects.filter(
                        membre=membre,
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                    mes_contributions_campagne_active = total_collecte_campagne_active

            # Progression de la campagne active
            progression = 0
            objectif_global_depasse = False
            if cotisation_active and cotisation_active.objectif_global:
                progression = (cotisation_active.montant_collecte / cotisation_active.objectif_global) * 100
                objectif_global_depasse = progression >= 100

            # Nombre d'enfants aidés
            nombre_enfants = Enfant.objects.filter(est_actif=True).count()

            # Taux de participation (campagne active)
            taux_participation_reel = 0
            taux_participation = 0
            objectif_depasse_par_membre = False
            objectif_global_atteint = False
            
            if cotisation_active and cotisation_active.objectif_global:
                taux_participation_reel = (mes_contributions_campagne_active / cotisation_active.objectif_global) * 100
                taux_participation = min(taux_participation_reel, 100)
                objectif_global_atteint = cotisation_active.montant_collecte >= cotisation_active.objectif_global
                objectif_depasse_par_membre = taux_participation_reel > 100 and objectif_global_atteint

            # Dernière contribution validée
            derniere_contribution = Payement.objects.filter(
                membre=request.user.membre,
                validee=True
            ).aggregate(derniere=Max('date_paiement'))['derniere']

            # Informations sur la cotisation active
            cotisation_info = None
            if cotisation_active:
                cotisation_info = {
                    'libelle': cotisation_active.libelle,
                    'annee': cotisation_active.annee,
                    'taux_realisation': float(cotisation_active.taux_realisation),
                    'objectif_global': float(cotisation_active.objectif_global),
                    'montant_collecte': float(cotisation_active.montant_collecte),
                    'objectif_depasse': cotisation_active.montant_collecte > cotisation_active.objectif_global
                }

            return JsonResponse({
                'is_tresorier': is_tresorier,
                'total_collecte_toutes_campagnes': float(total_collecte_toutes_campagnes),
                'mes_contributions_toutes_campagnes': float(mes_contributions_toutes_campagnes),
                'total_collecte_campagne_active': float(total_collecte_campagne_active),
                'mes_contributions_campagne_active': float(mes_contributions_campagne_active),
                'progression': float(progression),
                'nombre_enfants': nombre_enfants,
                'taux_participation': float(taux_participation),
                'taux_participation_reel': float(taux_participation_reel),
                'objectif_depasse_par_membre': objectif_depasse_par_membre,
                'objectif_global_atteint': objectif_global_atteint,
                'a_contribue': a_contribue,
                'derniere_contribution': derniere_contribution.strftime('%d %b %Y') if derniere_contribution else None,
                'objectif_global_depasse': objectif_global_depasse,
                'cotisation_active': cotisation_info
            })

        except Exception as e:
            logger.error(f"Erreur dashboard_stats: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Erreur lors du chargement des statistiques'}, status=500)
    
    return JsonResponse({'error': 'Requête invalide'}, status=400)

@login_required
def dashboard_charts_data(request):
    """Vue pour récupérer les données des graphiques en AJAX"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            from django.db.models import Count
            from datetime import datetime, timedelta
            import calendar

            membre = request.user.membre
            is_tresorier = MembreRoles.objects.filter(
                membre=membre,
                role__nom__iexact='trésorier',
                est_actif=True
            ).exists()

            # Données pour l'évolution des contributions (7 derniers jours)
            evolution_data = []
            labels = []
            
            for i in range(7):
                date = datetime.now() - timedelta(days=i)
                start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Filtrer selon le type d'utilisateur
                if is_tresorier:
                    # Trésoriers voient les données globales
                    montant_jour = Payement.objects.filter(
                        validee=True,
                        date_paiement__range=(start_date, end_date)
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                else:
                    # Membres normaux voient leurs propres données
                    montant_jour = Payement.objects.filter(
                        membre=membre,
                        validee=True,
                        date_paiement__range=(start_date, end_date)
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                
                evolution_data.insert(0, float(montant_jour))
                labels.insert(0, date.strftime('%d/%m'))

            # Données pour les moyens de paiement
            moyens_paiement_data = []
            moyens_paiement_labels = []
            
            # Filtrer selon le type d'utilisateur
            if is_tresorier:
                # Trésoriers voient les données globales
                moyens_paiement_stats = Payement.objects.filter(validee=True).values(
                    'moyen_paiement__libelle'
                ).annotate(
                    total=Sum('montant'),
                    count=Count('id')
                ).order_by('-total')
            else:
                # Membres normaux voient leurs propres données
                moyens_paiement_stats = Payement.objects.filter(
                    membre=membre,
                    validee=True
                ).values(
                    'moyen_paiement__libelle'
                ).annotate(
                    total=Sum('montant'),
                    count=Count('id')
                ).order_by('-total')

            for stat in moyens_paiement_stats:
                moyens_paiement_labels.append(stat['moyen_paiement__libelle'])
                moyens_paiement_data.append(float(stat['total']))

            # Données pour le top 5 des contributeurs (pour trésoriers uniquement)
            top_contributeurs_data = []
            top_contributeurs_labels = []
            top_contributeurs_original_names = []

            if is_tresorier:
                top_contributeurs_stats = Payement.objects.filter(validee=True).values(
                    'membre__nom', 'membre__prenom'
                ).annotate(
                    total=Sum('montant')
                ).order_by('-total')[:5]

                for stat in top_contributeurs_stats:
                    nom_complet = f"{stat['membre__nom']} {stat['membre__prenom']}"
                    nom_original = nom_complet
                    # Tronquer le nom si trop long (max 15 caractères)
                    if len(nom_complet) > 15:
                        nom_complet = nom_complet[:12] + "..."
                    top_contributeurs_labels.append(nom_complet)
                    top_contributeurs_original_names.append(nom_original)
                    top_contributeurs_data.append(float(stat['total']))

            # Vérifier si l'utilisateur a des données
            has_data = sum(evolution_data) > 0 or sum(moyens_paiement_data) > 0

            return JsonResponse({
                'evolution': {
                    'labels': labels,
                    'data': evolution_data
                },
                'moyens_paiement': {
                    'labels': moyens_paiement_labels,
                    'data': moyens_paiement_data
                },
                'top_contributeurs': {
                    'labels': top_contributeurs_labels,
                    'data': top_contributeurs_data,
                    'original_names': top_contributeurs_original_names
                } if is_tresorier else None,
                'is_tresorier': is_tresorier,
                'has_data': has_data
            })

        except Exception as e:
            logger.error(f"Erreur dashboard_charts_data: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Erreur lors du chargement des données graphiques'}, status=500)
    
    return JsonResponse({'error': 'Requête invalide'}, status=400)

@login_required
def dashboard_overview(request):
    """Vue pour la page vue d'ensemble du dashboard"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            membre = request.user.membre
            is_tresorier = MembreRoles.objects.filter(
                membre=membre,
                role__nom__iexact='trésorier',
                est_actif=True
            ).exists()

            cotisation_active = Cotisation.objects.filter(est_active=True).first()
            a_contribue = False

            if cotisation_active:
                a_contribue = Payement.objects.filter(
                    membre=request.user.membre,
                    cotisation=cotisation_active,
                    validee=True
                ).exists()

            # Total collecté (global ou personnel) - TOUTES LES CAMPAGNES
            if is_tresorier:
                total_collecte_toutes_campagnes = Payement.objects.filter(validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
                mes_contributions_toutes_campagnes = Payement.objects.filter(membre=membre, validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
            else:
                total_collecte_toutes_campagnes = Payement.objects.filter(membre=membre, validee=True).aggregate(Sum('montant'))['montant__sum'] or 0
                mes_contributions_toutes_campagnes = total_collecte_toutes_campagnes

            # Données de la campagne active uniquement
            total_collecte_campagne_active = 0
            mes_contributions_campagne_active = 0
            if cotisation_active:
                if is_tresorier:
                    total_collecte_campagne_active = Payement.objects.filter(
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                    mes_contributions_campagne_active = Payement.objects.filter(
                        membre=membre,
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                else:
                    total_collecte_campagne_active = Payement.objects.filter(
                        membre=membre,
                        cotisation=cotisation_active,
                        validee=True
                    ).aggregate(Sum('montant'))['montant__sum'] or 0
                    mes_contributions_campagne_active = total_collecte_campagne_active

            # Progression de la campagne active
            progression = 0
            objectif_global_depasse = False
            if cotisation_active and cotisation_active.objectif_global:
                progression = (cotisation_active.montant_collecte / cotisation_active.objectif_global) * 100
                objectif_global_depasse = progression >= 100

            # Nombre d'enfants aidés
            nombre_enfants = Enfant.objects.filter(est_actif=True).count()

            # Taux de participation (campagne active)
            taux_participation_reel = 0
            taux_participation = 0
            objectif_depasse_par_membre = False
            objectif_global_atteint = False
            
            if cotisation_active and cotisation_active.objectif_global:
                taux_participation_reel = (mes_contributions_campagne_active / cotisation_active.objectif_global) * 100
                taux_participation = min(taux_participation_reel, 100)
                objectif_global_atteint = cotisation_active.montant_collecte >= cotisation_active.objectif_global
                objectif_depasse_par_membre = taux_participation_reel > 100 and objectif_global_atteint

            # Dernière contribution validée
            derniere_contribution = Payement.objects.filter(
                membre=request.user.membre,
                validee=True
            ).aggregate(derniere=Max('date_paiement'))['derniere']

            # Informations sur la cotisation active
            cotisation_info = None
            if cotisation_active:
                cotisation_info = {
                    'libelle': cotisation_active.libelle,
                    'annee': cotisation_active.annee,
                    'taux_realisation': float(cotisation_active.taux_realisation),
                    'objectif_global': float(cotisation_active.objectif_global),
                    'montant_collecte': float(cotisation_active.montant_collecte),
                    'objectif_depasse': cotisation_active.montant_collecte > cotisation_active.objectif_global
                }

            context = {
                'is_tresorier': is_tresorier,
                'total_collecte_toutes_campagnes': float(total_collecte_toutes_campagnes),
                'mes_contributions_toutes_campagnes': float(mes_contributions_toutes_campagnes),
                'total_collecte_campagne_active': float(total_collecte_campagne_active),
                'mes_contributions_campagne_active': float(mes_contributions_campagne_active),
                'progression': float(progression),
                'nombre_enfants': nombre_enfants,
                'taux_participation': float(taux_participation),
                'taux_participation_reel': float(taux_participation_reel),
                'objectif_depasse_par_membre': objectif_depasse_par_membre,
                'objectif_global_atteint': objectif_global_atteint,
                'a_contribue': a_contribue,
                'derniere_contribution': derniere_contribution.strftime('%d %b %Y') if derniere_contribution else None,
                'objectif_global_depasse': objectif_global_depasse,
                'cotisation_active': cotisation_info
            }

            html = render_to_string('gestion/partials/dashboard_overview.html', context)
            return JsonResponse({'html': html})

        except Exception as e:
            logger.error(f"Erreur dashboard_overview: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Erreur lors du chargement de la vue d\'ensemble'}, status=500)
    
    return JsonResponse({'error': 'Requête invalide'}, status=400)

