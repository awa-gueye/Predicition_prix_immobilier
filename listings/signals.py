from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db import OperationalError, ProgrammingError


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
    except (OperationalError, ProgrammingError):
        # Table pas encore créée (premier migrate)
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
        # Table listings_userprofile pas encore créée
        pass
    except Exception:
        pass