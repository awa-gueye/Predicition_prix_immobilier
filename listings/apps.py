from django.apps import AppConfig


class ListingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'listings'
    verbose_name       = 'Annonces & Profils'

    def ready(self):
        import listings.signals  # noqa
