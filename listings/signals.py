"""
listings/signals.py
Signaux pour créer des alertes automatiquement.
"""
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db import OperationalError, ProgrammingError
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
    except (OperationalError, ProgrammingError):
        pass
    except Exception:
        pass


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        from .models import UserProfile
        profile = UserProfile.objects.filter(user=instance).first()
        if profile:
            profile.save()
    except (OperationalError, ProgrammingError):
        pass
    except Exception:
        pass


def notify_on_new_listing(sender, instance, created, **kwargs):
    """Crée des alertes pour les utilisateurs quand un bien est publié."""
    if not created:
        return
    try:
        from .models import UserProfile, Alert
        listing = instance
        listing_city = (listing.city or '').strip().lower()
        if not listing_city:
            return

        # Trouver tous les utilisateurs dans cette ville
        profiles = UserProfile.objects.filter(
            alerts_enabled=True,
            city__iexact=listing.city
        ).exclude(user=listing.seller).select_related('user')

        for profile in profiles[:50]:
            Alert.objects.create(
                user=profile.user,
                alert_type='new_listing',
                title=f"Nouveau bien à {listing.city}",
                message=f"{listing.title} — {listing.price_formatted}",
                property_title=listing.title[:200],
                property_price=listing.price,
                property_city=listing.city,
            )
        
        # Notifier aussi les utilisateurs avec une ville similaire
        profiles_nearby = UserProfile.objects.filter(
            alerts_enabled=True,
        ).exclude(
            user=listing.seller
        ).exclude(
            city__iexact=listing.city
        ).select_related('user')
        
        for profile in profiles_nearby[:20]:
            if profile.city and listing_city[:4] in profile.city.lower():
                Alert.objects.create(
                    user=profile.user,
                    alert_type='proximity',
                    title=f"Bien à proximité : {listing.city}",
                    message=f"{listing.title} — {listing.price_formatted}",
                    property_title=listing.title[:200],
                    property_price=listing.price,
                    property_city=listing.city,
                )

        logger.info(f"Alertes créées pour le bien: {listing.title}")
    except Exception as e:
        logger.warning(f"notify_on_new_listing: {e}")


def notify_admin_new_contact(contact_msg):
    """Notifie les admins quand un message contact est reçu."""
    try:
        from .models import Alert
        admins = User.objects.filter(is_superuser=True)
        for admin in admins:
            Alert.objects.create(
                user=admin,
                alert_type='admin_message',
                title=f"Nouveau message de {contact_msg.first_name}",
                message=f"{contact_msg.subject or 'Sans objet'}: {contact_msg.message[:100]}",
            )
    except Exception as e:
        logger.warning(f"notify_admin_new_contact: {e}")


# Connect the listing signal
try:
    from .models import Listing
    post_save.connect(notify_on_new_listing, sender=Listing)
except Exception:
    pass
