"""
listings/models.py
Modèles pour les annonces des vendeurs et le profil utilisateur étendu.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class UserProfile(models.Model):
    """Extension du modèle User Django."""
    ROLE_CHOICES = [
        ('user',   'Utilisateur'),
        ('seller', 'Vendeur'),
    ]
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone       = models.CharField(max_length=20, blank=True)
    role        = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    avatar      = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio         = models.TextField(blank=True)
    city        = models.CharField(max_length=100, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return '/static/immoanalytics/img/avatar_default.png'

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    class Meta:
        verbose_name        = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"


class Listing(models.Model):
    """Annonce ajoutée par un vendeur."""
    TYPE_CHOICES = [
        ('chambre',      'Chambre'),
        ('studio',       'Studio'),
        ('appartement',  'Appartement'),
        ('villa',        'Villa'),
        ('maison',       'Maison'),
        ('duplex',       'Duplex'),
        ('terrain',      'Terrain'),
        ('bureau',       'Bureau / Local commercial'),
        ('immeuble',     'Immeuble'),
    ]
    TXN_CHOICES = [
        ('vente',    'Vente'),
        ('location', 'Location'),
    ]
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('pending',  'En attente de validation'),
        ('sold',     'Vendu / Loué'),
        ('inactive', 'Désactivée'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    title        = models.CharField(max_length=200)
    description  = models.TextField()
    property_type= models.CharField(max_length=20, choices=TYPE_CHOICES)
    transaction  = models.CharField(max_length=10, choices=TXN_CHOICES)
    price        = models.BigIntegerField()
    surface_area = models.FloatField(null=True, blank=True)
    bedrooms     = models.IntegerField(null=True, blank=True)
    bathrooms    = models.IntegerField(null=True, blank=True)
    city         = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=100, blank=True)
    address      = models.CharField(max_length=255, blank=True)
    latitude     = models.FloatField(null=True, blank=True)
    longitude    = models.FloatField(null=True, blank=True)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    views_count  = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = "Annonce"
        verbose_name_plural = "Annonces"

    def __str__(self):
        return f"{self.title} — {self.price:,} FCFA ({self.city})"

    @property
    def main_image(self):
        img = self.images.filter(is_main=True).first()
        if not img:
            img = self.images.first()
        return img

    @property
    def price_formatted(self):
        p = self.price
        if p >= 1_000_000_000: return f"{p/1e9:.2f} Mds FCFA"
        if p >= 1_000_000:     return f"{p/1e6:.1f}M FCFA"
        if p >= 1_000:         return f"{p/1e3:.0f}K FCFA"
        return f"{p:,} FCFA"

    @property
    def price_unit(self):
        return "/mois" if self.transaction == "location" else ""


class ListingImage(models.Model):
    """Images associées à une annonce vendeur."""
    listing  = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image    = models.ImageField(upload_to='listings/')
    caption  = models.CharField(max_length=200, blank=True)
    is_main  = models.BooleanField(default=False)
    order    = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering            = ['order', 'id']
        verbose_name        = "Image d'annonce"
        verbose_name_plural = "Images d'annonces"

    def __str__(self):
        return f"Image {self.order} — {self.listing.title}"
