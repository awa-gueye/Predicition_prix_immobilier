from rest_framework import serializers
from .models import (
    CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty,
    DakarVenteProperty, ImmoSenegalProperty,
)


class CoinAfriqueSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CoinAfriqueProperty
        fields = '__all__'


class ExpatDakarSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExpatDakarProperty
        fields = '__all__'


class LogerDakarSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LogerDakarProperty
        fields = '__all__'


class DakarVenteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DakarVenteProperty
        fields = '__all__'


class ImmoSenegalSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ImmoSenegalProperty
        fields = '__all__'


class PropertyUnifiedSerializer(serializers.Serializer):
    """
    Sérialiseur unifié — champs communs à toutes les sources.
    Utilisé par AllPropertiesView et la prédiction ML.
    """
    id            = serializers.CharField()
    title         = serializers.CharField(allow_null=True)
    price         = serializers.IntegerField(allow_null=True)
    surface_area  = serializers.FloatField(allow_null=True)
    bedrooms      = serializers.IntegerField(allow_null=True)
    bathrooms     = serializers.IntegerField(allow_null=True)
    city          = serializers.CharField(allow_null=True)
    property_type = serializers.CharField(allow_null=True)
    source        = serializers.CharField()
    url           = serializers.CharField()
    scraped_at    = serializers.DateTimeField(allow_null=True)
