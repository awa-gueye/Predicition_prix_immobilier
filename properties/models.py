from django.db import models


class CoinAfriqueProperty(models.Model):
    """
    Correspond à la table 'coinafriqure' créée par CoinsafriquePostgreSQLPipeline.
    """
    id            = models.CharField(max_length=32, primary_key=True)
    url           = models.TextField(unique=True)
    title         = models.TextField(null=True, blank=True)
    price         = models.IntegerField(null=True, blank=True)
    surface_area  = models.FloatField(null=True, blank=True)
    bedrooms      = models.IntegerField(null=True, blank=True)
    bathrooms     = models.IntegerField(null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    description   = models.TextField(null=True, blank=True)
    source        = models.CharField(max_length=50, null=True, blank=True)
    latitude      = models.FloatField(null=True, blank=True)
    longitude     = models.FloatField(null=True, blank=True)
    scraped_at    = models.DateTimeField(null=True, blank=True)
    statut        = models.CharField(max_length=50, null=True, blank=True)
    nb_annonces   = models.IntegerField(null=True, blank=True)
    posted_time   = models.CharField(max_length=100, null=True, blank=True)
    adresse       = models.CharField(max_length=100, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "coinafriqure"   # nom exact de la table Scrapy
        managed = False             # Django ne la crée/supprime pas (Scrapy s'en charge)
        verbose_name = "Annonce CoinAfrique"
        verbose_name_plural = "Annonces CoinAfrique"
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.title or 'Sans titre'} — {self.price} FCFA ({self.city})"


class ExpatDakarProperty(models.Model):
    """
    Correspond à la table 'expat_dakar_properties' créée par ExpatDakarPostgreSQLPipeline.
    """
    id            = models.CharField(max_length=32, primary_key=True)
    url           = models.TextField(unique=True)
    title         = models.TextField(null=True, blank=True)
    price         = models.IntegerField(null=True, blank=True)
    surface_area  = models.FloatField(null=True, blank=True)
    bedrooms      = models.IntegerField(null=True, blank=True)
    bathrooms     = models.IntegerField(null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    region        = models.CharField(max_length=100, null=True, blank=True)
    description   = models.TextField(null=True, blank=True)
    source        = models.CharField(max_length=50, null=True, blank=True)
    scraped_at    = models.DateTimeField(null=True, blank=True)
    statut        = models.CharField(max_length=50, null=True, blank=True)
    posted_time   = models.CharField(max_length=100, null=True, blank=True)
    adresse       = models.CharField(max_length=100, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    member_since  = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "expat_dakar_properties"
        managed = False
        verbose_name = "Annonce Expat-Dakar"
        verbose_name_plural = "Annonces Expat-Dakar"
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.title or 'Sans titre'} — {self.price} FCFA ({self.city})"


class LogerDakarProperty(models.Model):
    """
    Correspond à la table 'loger_dakar_properties' créée par LogerDakarPostgreSQLPipeline.
    """
    id            = models.CharField(max_length=32, primary_key=True)
    url           = models.TextField(unique=True)
    title         = models.TextField(null=True, blank=True)
    price         = models.IntegerField(null=True, blank=True)
    surface_area  = models.FloatField(null=True, blank=True)
    bedrooms      = models.IntegerField(null=True, blank=True)
    bathrooms     = models.IntegerField(null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    region        = models.CharField(max_length=100, null=True, blank=True)
    description   = models.TextField(null=True, blank=True)
    source        = models.CharField(max_length=50, null=True, blank=True)
    scraped_at    = models.DateTimeField(null=True, blank=True)
    statut        = models.CharField(max_length=50, null=True, blank=True)
    posted_time   = models.CharField(max_length=100, null=True, blank=True)
    adresse       = models.CharField(max_length=100, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    listing_id    = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "loger_dakar_properties"
        managed = False
        verbose_name = "Annonce Loger-Dakar"
        verbose_name_plural = "Annonces Loger-Dakar"
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.title or 'Sans titre'} — {self.price} FCFA ({self.city})"
    
class DakarVenteProperty(models.Model):
    """
    Correspond à la table 'dakarvente_properties'
    créée par DakarVentePostgreSQLPipeline.
    """
    id            = models.CharField(max_length=32, primary_key=True)
    url           = models.TextField(unique=True)
    title         = models.TextField(null=True, blank=True)
    price         = models.IntegerField(null=True, blank=True)
    surface_area  = models.FloatField(null=True, blank=True)
    bedrooms      = models.IntegerField(null=True, blank=True)
    bathrooms     = models.IntegerField(null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    adresse       = models.CharField(max_length=200, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    description   = models.TextField(null=True, blank=True)
    source        = models.CharField(max_length=50, null=True, blank=True)
    statut        = models.CharField(max_length=50, null=True, blank=True)
    latitude      = models.FloatField(null=True, blank=True)
    longitude     = models.FloatField(null=True, blank=True)
    scraped_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "dakarvente_properties"
        managed  = False
        verbose_name = "Annonce DakarVente"
        verbose_name_plural = "Annonces DakarVente"
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.title or 'Sans titre'} — {self.price} FCFA ({self.city})"

class ImmoSenegalProperty(models.Model):
    """
    Correspond à la table 'immosenegal_properties'
    créée par ImmoSenegalPostgreSQLPipeline.
    """
    id            = models.CharField(max_length=32, primary_key=True)
    url           = models.TextField(unique=True)
    title         = models.TextField(null=True, blank=True)
    price         = models.BigIntegerField(null=True, blank=True)
    surface_area  = models.FloatField(null=True, blank=True)
    bedrooms      = models.IntegerField(null=True, blank=True)
    bathrooms     = models.IntegerField(null=True, blank=True)
    garage        = models.IntegerField(null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    adresse       = models.CharField(max_length=200, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    transaction   = models.CharField(max_length=20, null=True, blank=True)
    description   = models.TextField(null=True, blank=True)
    source        = models.CharField(max_length=50, null=True, blank=True)
    statut        = models.CharField(max_length=50, null=True, blank=True)
    latitude      = models.FloatField(null=True, blank=True)
    longitude     = models.FloatField(null=True, blank=True)
    scraped_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "immosenegal_properties"
        managed  = False
        verbose_name = "Annonce ImmobilierSenegal"
        verbose_name_plural = "Annonces ImmobilierSenegal"
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.title or 'Sans titre'} — {self.price} FCFA ({self.city})"
    
# ─────────────────────────────────────────────────────────────────────────────
# Coller à la FIN de properties/models.py
# Tables Gold Layer — indicateurs agrégés calculés depuis les données brutes
# ─────────────────────────────────────────────────────────────────────────────


class PrixMedianQuartier(models.Model):
    """
    Table Gold — Prix médians agrégés par quartier et type de bien.
    Alimentée par une requête SQL exécutée dans Neon.
    """
    quartier         = models.CharField(max_length=100)
    type_bien        = models.CharField(max_length=100, null=True, blank=True)
    nb_observations  = models.IntegerField(null=True, blank=True)
    prix_median      = models.BigIntegerField(null=True, blank=True)
    prix_m2_median   = models.FloatField(null=True, blank=True)
    prix_min         = models.BigIntegerField(null=True, blank=True)
    prix_max         = models.BigIntegerField(null=True, blank=True)
    ecart_type       = models.FloatField(null=True, blank=True)
    source           = models.CharField(max_length=50, null=True, blank=True)
    date_calcul      = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "prix_medians_quartier"
        managed  = False
        verbose_name = "Prix médian par quartier"
        verbose_name_plural = "Prix médians par quartier"
        ordering = ["-nb_observations"]

    def __str__(self):
        return f"{self.quartier} — {self.type_bien} : {self.prix_median} FCFA"


class TendanceMensuelle(models.Model):
    """
    Table Gold — Évolution mensuelle des prix par quartier.
    """
    quartier       = models.CharField(max_length=100)
    mois           = models.IntegerField()
    annee          = models.IntegerField()
    prix_median    = models.BigIntegerField(null=True, blank=True)
    nb_annonces    = models.IntegerField(null=True, blank=True)
    variation_pct  = models.FloatField(null=True, blank=True)
    type_bien      = models.CharField(max_length=100, null=True, blank=True)
    source         = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "tendances_mensuelles"
        managed  = False
        verbose_name = "Tendance mensuelle"
        verbose_name_plural = "Tendances mensuelles"
        ordering = ["-annee", "-mois"]

    def __str__(self):
        return f"{self.quartier} — {self.mois}/{self.annee}"