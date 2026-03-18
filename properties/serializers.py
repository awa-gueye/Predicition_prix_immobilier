from rest_framework import serializers
from .models import CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty


class CoinAfriqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoinAfriqueProperty
        fields = '__all__'


class ExpatDakarSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpatDakarProperty
        fields = '__all__'


class LogerDakarSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogerDakarProperty
        fields = '__all__'


class PropertyUnifiedSerializer(serializers.Serializer):
    """
    Serializer unifié pour agréger les annonces des 3 sources.
    Contient uniquement les champs communs utiles pour le ML.
    """
    id           = serializers.CharField()
    title        = serializers.CharField()
    price        = serializers.IntegerField()
    surface_area = serializers.FloatField()
    bedrooms     = serializers.IntegerField()
    bathrooms    = serializers.IntegerField()
    city         = serializers.CharField()
    property_type = serializers.CharField()
    source       = serializers.CharField()
    url          = serializers.CharField()
    scraped_at   = serializers.DateTimeField()