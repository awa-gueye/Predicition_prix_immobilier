from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Listing, ListingImage


class RegisterForm(forms.Form):
    username   = forms.CharField(max_length=30, label="Nom d'utilisateur")
    first_name = forms.CharField(max_length=50, label="Prénom")
    last_name  = forms.CharField(max_length=50, label="Nom")
    email      = forms.EmailField(label="Email")
    phone      = forms.CharField(max_length=20, label="Téléphone")
    password1  = forms.CharField(widget=forms.PasswordInput, label="Mot de passe")
    password2  = forms.CharField(widget=forms.PasswordInput, label="Confirmer le mot de passe")

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return u

    def clean(self):
        cd = super().clean()
        if cd.get('password1') != cd.get('password2'):
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        if len(cd.get('password1','')) < 8:
            raise forms.ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
        return cd


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=False, label="Prénom")
    last_name  = forms.CharField(max_length=50, required=False, label="Nom")
    email      = forms.EmailField(required=False, label="Email")

    class Meta:
        model  = UserProfile
        fields = ['phone','role','bio','city','avatar']
        labels = {
            'phone':  'Téléphone',
            'role':   'Statut du compte',
            'bio':    'Biographie',
            'city':   'Ville',
            'avatar': 'Photo de profil',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }


class ListingForm(forms.ModelForm):
    class Meta:
        model  = Listing
        fields = ['title','description','property_type','transaction','price',
                  'surface_area','bedrooms','bathrooms','city','neighborhood',
                  'address','latitude','longitude']
        labels = {
            'title':         'Titre de l\'annonce',
            'description':   'Description',
            'property_type': 'Type de bien',
            'transaction':   'Type de transaction',
            'price':         'Prix (FCFA)',
            'surface_area':  'Superficie (m²)',
            'bedrooms':      'Nombre de chambres',
            'bathrooms':     'Nombre de salles de bain',
            'city':          'Ville',
            'neighborhood':  'Quartier',
            'address':       'Adresse complète',
            'latitude':      'Latitude (optionnel)',
            'longitude':     'Longitude (optionnel)',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def clean_price(self):
        p = self.cleaned_data.get('price', 0)
        if p <= 0:
            raise forms.ValidationError("Le prix doit être supérieur à 0.")
        return p


class ListingImageForm(forms.ModelForm):
    class Meta:
        model  = ListingImage
        fields = ['image', 'caption', 'is_main']
        labels = {
            'image':   'Image',
            'caption': 'Légende (optionnel)',
            'is_main': 'Image principale',
        }
