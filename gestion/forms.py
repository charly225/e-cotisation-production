from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User

from .models import Temoignage, Payement, Cotisation, MoyenPaiement, Membre


class TemoignagePublicForm(forms.ModelForm):
    class Meta:
        model = Temoignage
        fields = ['nom', 'lien_avec_enfant', 'message', 'nombre_etoiles']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
            'nombre_etoiles': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }


# Formulaire d'inscription
class RegisterForm(forms.ModelForm):
    nom_complet = forms.CharField(max_length=100, label="Nom complet")
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'nom_complet', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet email.")
        return email


# Formulaire de connexion
class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Nom d'utilisateur")
    password = forms.CharField(widget=forms.PasswordInput, label='Mot de passe')

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Payement
        fields = ['cotisation', 'montant', 'moyen_paiement']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['cotisation'].queryset = Cotisation.objects.filter(est_active=True)
        self.fields['moyen_paiement'].queryset = MoyenPaiement.objects.filter(est_actif=True)

        # En mode POST, analyser la cotisation choisie
        data = self.data or self.initial
        cotisation_id = data.get('cotisation')

        if cotisation_id:
            try:
                cotisation = Cotisation.objects.get(id=cotisation_id)
                param = getattr(cotisation, 'parametragecotisation', None)

                if param:
                    if not param.est_cotisation_libre:
                        montant = param.montant_fixe or 0
                        self.fields['montant'].initial = montant
                        self.fields['montant'].widget.attrs.update({
                            'readonly': True,
                            'class': 'form-input w-full px-4 py-2 rounded-md bg-gray-100 text-gray-500 cursor-not-allowed'
                        })
                    else:
                        # Champ modifiable avec minimum
                        self.fields['montant'].widget.attrs.update({
                            'placeholder': f'Montant min: {param.montant_minimum or 0} FCFA',
                            'min': param.montant_minimum or 0,
                            'step': '100',
                            'class': 'form-input w-full px-4 py-2 rounded-md'
                        })

            except (ValueError, Cotisation.DoesNotExist):
                pass

class ProfilForm(forms.ModelForm):
    class Meta:
        model = Membre
        fields = ['nom', 'prenom', 'telephone', 'email']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            }),
        }

class EmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

class PasswordUpdateForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            })