from django.contrib import admin
from .models import CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty


@admin.register(CoinAfriqueProperty)
class CoinAfriqueAdmin(admin.ModelAdmin):
    list_display  = ("title", "price", "city", "property_type", "surface_area", "bedrooms", "scraped_at")
    list_filter   = ("city", "property_type", "statut")
    search_fields = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")


@admin.register(ExpatDakarProperty)
class ExpatDakarAdmin(admin.ModelAdmin):
    list_display  = ("title", "price", "city", "region", "property_type", "surface_area", "bedrooms", "scraped_at")
    list_filter   = ("city", "region", "property_type", "statut")
    search_fields = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")


@admin.register(LogerDakarProperty)
class LogerDakarAdmin(admin.ModelAdmin):
    list_display  = ("title", "price", "city", "region", "property_type", "surface_area", "bedrooms", "scraped_at")
    list_filter   = ("city", "region", "property_type", "statut")
    search_fields = ("title", "adresse", "city")
    readonly_fields = ("id", "url", "scraped_at")
