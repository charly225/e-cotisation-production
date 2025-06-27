from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import accueil, auth, effectuer_paiement, get_parametrage_cotisation, dashboard, historique_paiements, \
 campagne_courante, modifier_profil, valider_paiement, paiements_a_valider, valider_tous_les_paiements, paiements_valides_par_moi, \
 statut_cotisation, chargement

urlpatterns = [
 path('', chargement, name='chargement'),
 path('accueil/', accueil, name='accueil'),
 path('auth/', auth, name='auth'),
 path('logout/', LogoutView.as_view(next_page='accueil'), name='logout'),
 path('paiement/', effectuer_paiement, name='effectuer_paiement'),
 path('cotisation/parametrage/<int:cotisation_id>/', get_parametrage_cotisation, name='get_parametrage_cotisation'),
 path('dashboard/', dashboard, name='dashboard'),
 path('dashboard/historique/', historique_paiements, name="historique_paiements"),
 path("dashboard/campagne/", campagne_courante, name="campagne_courante"),
 path('profil/', modifier_profil, name='modifier_profil'),
 path('paiements-a-valider/', paiements_a_valider, name='paiements_a_valider'),
 path('valider-paiement/<int:pk>/', valider_paiement, name='valider_paiement'),
 path('paiements/valider_tous/', valider_tous_les_paiements, name='valider_tous_les_paiements'),
 path('paiements-valides/', paiements_valides_par_moi, name='paiements_valides_par_moi'),
 path('ajax/statut-cotisation/<int:cotisation_id>/', statut_cotisation, name='statut_cotisation'),
]