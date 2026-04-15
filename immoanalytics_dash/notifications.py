"""
ImmoPredict SN — notifications.py
Système de notifications email + plateforme.
Envoie des alertes quand de nouveaux biens correspondent aux recherches des utilisateurs.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def notify_users_new_listings():
    """
    Vérifie les nouvelles annonces et notifie les utilisateurs concernés.
    À appeler périodiquement (cron, Celery, ou management command).
    """
    try:
        from listings.models import UserProfile, Listing, Alert

        profiles = UserProfile.objects.filter(alerts_enabled=True).select_related('user')
        if not profiles.exists():
            return 0

        # Annonces des dernières 24h
        since = timezone.now() - timezone.timedelta(hours=24)
        new_listings = Listing.objects.filter(
            created_at__gte=since, status='active'
        ).order_by('-created_at')[:50]

        if not new_listings.exists():
            return 0

        count = 0
        for profile in profiles:
            user = profile.user
            user_city = (profile.city or '').strip().lower()
            if not user_city:
                continue

            # Trouver les biens dans la ville de l'utilisateur
            matching = [l for l in new_listings
                       if user_city in (l.city or '').lower()]

            if not matching:
                continue

            # Créer une alerte sur la plateforme
            for listing in matching[:5]:
                Alert.objects.get_or_create(
                    user=user,
                    listing=listing,
                    alert_type='new_listing',
                    defaults={
                        'title': f"Nouveau bien à {listing.city}",
                        'message': f"{listing.title} — {listing.price_formatted}",
                        'property_city': listing.city,
                        'property_price': listing.price,
                        'property_title': listing.title[:200],
                    }
                )

            # Envoyer un email récapitulatif
            if user.email and matching:
                try:
                    subject = f"ImmoPredict SN — {len(matching)} nouveau(x) bien(s) à {user_city.title()}"
                    
                    body_lines = [
                        f"Bonjour {user.first_name or user.username},\n",
                        f"De nouveaux biens correspondent à votre profil ({user_city.title()}) :\n",
                    ]
                    for l in matching[:5]:
                        body_lines.append(
                            f"  • {l.title} — {l.price_formatted} ({l.get_property_type_display()})"
                        )
                    body_lines.extend([
                        f"\nConsultez-les sur ImmoPredict SN :",
                        f"https://immopredict.onrender.com/vente/",
                        f"\n— L'équipe ImmoPredict SN"
                    ])

                    send_mail(
                        subject=subject,
                        message="\n".join(body_lines),
                        from_email=settings.DEFAULT_FROM_EMAIL or "noreply@immopredict.sn",
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                    count += 1
                    logger.info(f"Email envoyé à {user.email}")
                except Exception as e:
                    logger.warning(f"Email error for {user.email}: {e}")

        return count

    except Exception as e:
        logger.error(f"notify_users_new_listings: {e}")
        return 0


def notify_matching_searches(user, new_listings=None):
    """
    Notifie un utilisateur spécifique si des biens correspondent à ses recherches récentes.
    """
    try:
        from listings.models import UserProfile, Alert

        profile = UserProfile.objects.get(user=user)
        if not profile.alerts_enabled:
            return

        user_city = (profile.city or '').strip().lower()

        # Chercher dans les données scrapées
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
                                       LogerDakarProperty, DakarVenteProperty)
        
        recent_props = []
        for model in [CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty, DakarVenteProperty]:
            try:
                qs = model.objects.filter(price__gte=500_000).order_by('-id')
                if user_city:
                    qs = qs.filter(city__icontains=user_city[:6])
                for p in qs.values('title', 'price', 'city', 'property_type')[:3]:
                    recent_props.append(p)
            except:
                continue

        for prop in recent_props[:5]:
            Alert.objects.get_or_create(
                user=user,
                alert_type='recommendation',
                property_title=str(prop.get('title', ''))[:200],
                defaults={
                    'title': f"Recommandé pour vous",
                    'message': f"{prop.get('title','')} — {prop.get('city','')}",
                    'property_price': prop.get('price'),
                    'property_city': str(prop.get('city', '')),
                }
            )

    except Exception as e:
        logger.warning(f"notify_matching_searches: {e}")
