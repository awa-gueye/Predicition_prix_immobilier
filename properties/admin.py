from django.contrib import admin
from .models import (
    CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty,
    DakarVenteProperty, ImmoSenegalProperty,
    PrixMedianQuartier, TendanceMensuelle,
)


@admin.register(CoinAfriqueProperty)
class CoinAfriqueAdmin(admin.ModelAdmin):
    list_display    = ("title", "price", "city", "property_type",
                       "surface_area", "bedrooms", "statut", "scraped_at")
    list_filter     = ("city", "property_type", "statut")
    search_fields   = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")
    ordering        = ("-scraped_at",)


@admin.register(ExpatDakarProperty)
class ExpatDakarAdmin(admin.ModelAdmin):
    list_display    = ("title", "price", "city", "region",
                       "property_type", "surface_area", "bedrooms", "scraped_at")
    list_filter     = ("city", "region", "property_type", "statut")
    search_fields   = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")
    ordering        = ("-scraped_at",)


@admin.register(LogerDakarProperty)
class LogerDakarAdmin(admin.ModelAdmin):
    list_display    = ("title", "price", "city", "region",
                       "property_type", "surface_area", "bedrooms", "scraped_at")
    list_filter     = ("city", "region", "property_type", "statut")
    search_fields   = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")
    ordering        = ("-scraped_at",)


@admin.register(DakarVenteProperty)
class DakarVenteAdmin(admin.ModelAdmin):
    list_display    = ("title", "price", "city", "property_type",
                       "surface_area", "bedrooms", "statut", "scraped_at")
    list_filter     = ("city", "property_type", "statut")
    search_fields   = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at", "latitude", "longitude")
    ordering        = ("-scraped_at",)


@admin.register(ImmoSenegalProperty)
class ImmoSenegalAdmin(admin.ModelAdmin):
    list_display    = ("title", "price", "city", "property_type",
                       "surface_area", "bedrooms", "transaction", "scraped_at")
    list_filter     = ("city", "property_type", "transaction", "statut")
    search_fields   = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at", "latitude", "longitude")
    ordering        = ("-scraped_at",)


@admin.register(PrixMedianQuartier)
class PrixMedianQuartierAdmin(admin.ModelAdmin):
    list_display  = ("quartier", "type_bien", "prix_median",
                     "prix_m2_median", "nb_observations", "date_calcul")
    list_filter   = ("type_bien", "source")
    search_fields = ("quartier",)
    ordering      = ("-nb_observations",)


@admin.register(TendanceMensuelle)
class TendanceMensuelleAdmin(admin.ModelAdmin):
    list_display  = ("quartier", "mois", "annee", "prix_median",
                     "nb_annonces", "variation_pct", "type_bien")
    list_filter   = ("annee", "type_bien", "source")
    search_fields = ("quartier",)
    ordering      = ("-annee", "-mois")
