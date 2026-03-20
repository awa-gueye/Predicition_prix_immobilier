"""
Configuration de l'app Django immoanalytics_dash.

Applique un patch sur DjangoDash pour corriger le bug 'caller_module is None'
qui apparaît quand les apps Dash sont importées depuis apps.py.ready().
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


def _patch_django_plotly_dash():
    """
    Patch DjangoDash.__init__ pour éviter l'AttributeError 'caller_module is None'.

    Cause : inspect.getmodule() retourne None quand le module est chargé
    dynamiquement via apps.ready(). Le patch assigne un module par défaut
    (django_plotly_dash.dash_wrapper) quand caller_module est None.
    """
    try:
        import inspect as _inspect
        from django_plotly_dash import DjangoDash
        import django_plotly_dash.dash_wrapper as _dw

        _original_init = DjangoDash.__init__

        def _patched_init(self, *args, **kwargs):
            _original_init(self, *args, **kwargs)
            # Corriger caller_module si None (bug import dynamique)
            if self.caller_module is None:
                self.caller_module = _dw
                logger.debug("DjangoDash: caller_module patché -> django_plotly_dash.dash_wrapper")

        DjangoDash.__init__ = _patched_init
        logger.info("Patch DjangoDash.caller_module appliqué.")

    except Exception as e:
        logger.warning(f"Impossible d'appliquer le patch DjangoDash : {e}")


class ImmoAnalyticsDashConfig(AppConfig):
    name               = 'immoanalytics_dash'
    verbose_name       = 'ImmoAnalytics Dashboards'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        1. Applique le patch caller_module
        2. Importe les modules dash_apps (ce qui déclenche l'enregistrement
           de chaque DjangoDash au niveau module)
        """
        # Patch en premier, avant tout import DjangoDash
        _patch_django_plotly_dash()

        try:
            from . import dash_apps  # noqa
        except Exception as e:
            logger.error(f"Erreur chargement dashboards Dash : {e}")
