from rest_framework import generics, filters
from rest_framework.views     import APIView
from rest_framework.response  import Response
from django.db.models         import Avg, Min, Max, Count
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.decorators  import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import (
    CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty,
    DakarVenteProperty,
    PrixMedianQuartier, TendanceMensuelle,
)
from .serializers import (
    CoinAfriqueSerializer, ExpatDakarSerializer, LogerDakarSerializer,
    DakarVenteSerializer, PropertyUnifiedSerializer,
)


# ── CoinAfrique ───────────────────────────────────────────────────────────────

class CoinAfriqueListView(generics.ListAPIView):
    """
    Liste toutes les annonces CoinAfrique.
    Filtres    : city, property_type, statut
    Recherche  : title, adresse
    Tri        : price, surface_area, scraped_at
    Params sup.: min_price, max_price, min_surface
    """
    serializer_class = CoinAfriqueSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'property_type', 'statut']
    search_fields    = ['title', 'adresse']
    ordering_fields  = ['price', 'surface_area', 'scraped_at']
    ordering         = ['-scraped_at']

    def get_queryset(self):
        qs = CoinAfriqueProperty.objects.exclude(price__isnull=True)
        mp  = self.request.query_params.get('min_price')
        xp  = self.request.query_params.get('max_price')
        ms  = self.request.query_params.get('min_surface')
        if mp:  qs = qs.filter(price__gte=mp)
        if xp:  qs = qs.filter(price__lte=xp)
        if ms:  qs = qs.filter(surface_area__gte=ms)
        return qs


class CoinAfriqueDetailView(generics.RetrieveAPIView):
    queryset         = CoinAfriqueProperty.objects.all()
    serializer_class = CoinAfriqueSerializer


# ── Expat-Dakar ───────────────────────────────────────────────────────────────

class ExpatDakarListView(generics.ListAPIView):
    """
    Liste toutes les annonces Expat-Dakar.
    Filtres    : city, region, property_type, statut
    Params sup.: min_price, max_price
    """
    serializer_class = ExpatDakarSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'region', 'property_type', 'statut']
    search_fields    = ['title', 'adresse']
    ordering_fields  = ['price', 'surface_area', 'scraped_at']
    ordering         = ['-scraped_at']

    def get_queryset(self):
        qs = ExpatDakarProperty.objects.exclude(price__isnull=True)
        mp = self.request.query_params.get('min_price')
        xp = self.request.query_params.get('max_price')
        if mp: qs = qs.filter(price__gte=mp)
        if xp: qs = qs.filter(price__lte=xp)
        return qs


class ExpatDakarDetailView(generics.RetrieveAPIView):
    queryset         = ExpatDakarProperty.objects.all()
    serializer_class = ExpatDakarSerializer


# ── Loger-Dakar ───────────────────────────────────────────────────────────────

class LogerDakarListView(generics.ListAPIView):
    """Liste toutes les annonces Loger-Dakar."""
    serializer_class = LogerDakarSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'region', 'property_type', 'statut']
    search_fields    = ['title', 'adresse']
    ordering_fields  = ['price', 'surface_area', 'scraped_at']
    ordering         = ['-scraped_at']

    def get_queryset(self):
        return LogerDakarProperty.objects.exclude(price__isnull=True)


class LogerDakarDetailView(generics.RetrieveAPIView):
    queryset         = LogerDakarProperty.objects.all()
    serializer_class = LogerDakarSerializer


# ── DakarVente ────────────────────────────────────────────────────────────────

class DakarVenteListView(generics.ListAPIView):
    """Liste toutes les annonces DakarVente."""
    serializer_class = DakarVenteSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'property_type', 'statut']
    search_fields    = ['title', 'adresse']
    ordering_fields  = ['price', 'surface_area', 'scraped_at']
    ordering         = ['-scraped_at']

    def get_queryset(self):
        qs = DakarVenteProperty.objects.exclude(price__isnull=True)
        mp = self.request.query_params.get('min_price')
        xp = self.request.query_params.get('max_price')
        if mp: qs = qs.filter(price__gte=mp)
        if xp: qs = qs.filter(price__lte=xp)
        return qs


class DakarVenteDetailView(generics.RetrieveAPIView):
    queryset         = DakarVenteProperty.objects.all()
    serializer_class = DakarVenteSerializer




# ── Vue unifiée — toutes les sources ─────────────────────────────────────────

class AllPropertiesView(APIView):
    """
    Agrège les annonces des 5 sources en une réponse unifiée.
    Seuls les champs communs sont retournés (utile pour le ML).

    Query params :
        source : coinafrique | expat_dakar | loger_dakar | dakarvente | immosenegal | all (défaut)
    """
    def get(self, request):
        source = request.query_params.get('source', 'all')

        def extract(obj, src):
            return {
                'id':            obj.id,
                'title':         obj.title,
                'price':         obj.price,
                'surface_area':  obj.surface_area,
                'bedrooms':      obj.bedrooms,
                'bathrooms':     obj.bathrooms,
                'city':          obj.city,
                'property_type': obj.property_type,
                'source':        src,
                'url':           obj.url,
                'scraped_at':    obj.scraped_at,
            }

        SOURCES = {
            'coinafrique': (CoinAfriqueProperty, 'coinafrique'),
            'expat_dakar': (ExpatDakarProperty,  'expat_dakar'),
            'loger_dakar': (LogerDakarProperty,  'loger_dakar'),
            'dakarvente':  (DakarVenteProperty,  'dakarvente'),
        }

        results = []
        for key, (model, label) in SOURCES.items():
            if source in ('all', key):
                try:
                    for obj in model.objects.exclude(price__isnull=True)[:1000]:
                        results.append(extract(obj, label))
                except Exception:
                    pass

        return Response({'count': len(results), 'results': results})


# ── Statistiques globales ─────────────────────────────────────────────────────

class StatsView(APIView):
    """
    Statistiques descriptives sur les données collectées par source.
    Retourne pour chaque source : total, prix moyen/min/max, surface moyenne.
    """
    def get(self, request):

        def stats(model, name):
            try:
                qs = model.objects.exclude(price__isnull=True)
                return qs.aggregate(
                    total           = Count('id'),
                    prix_moyen      = Avg('price'),
                    prix_min        = Min('price'),
                    prix_max        = Max('price'),
                    surface_moyenne = Avg('surface_area'),
                )
            except Exception as e:
                return {'error': str(e).split("\n")[0], 'total': 0}

        sources = [
            ('coinafrique', CoinAfriqueProperty),
            ('expat_dakar', ExpatDakarProperty),
            ('loger_dakar', LogerDakarProperty),
            ('dakarvente',  DakarVenteProperty),
        ]
        return Response({name: stats(model, name) for name, model in sources})


# ── Prédiction ML ─────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class PredictPriceView(APIView):
    """
    Prédit le prix d'un bien à partir de ses caractéristiques.
    POST /api/properties/predict/

    Body JSON :
        city, property_type, surface_area, bedrooms, bathrooms,
        source (optionnel), latitude, longitude (optionnels)
    """
    def post(self, request):
        import os, sys, importlib

        ml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml')
        if ml_dir not in sys.path:
            sys.path.insert(0, ml_dir)

        try:
            predict_module = importlib.import_module('predict')
            predict_price  = predict_module.predict_price
        except ModuleNotFoundError:
            return Response(
                {'error': "Modèle ML non trouvé. Exécutez d'abord le Notebook 4."},
                status=503
            )

        data = request.data
        try:
            result = predict_price(
                surface_area  = data.get('surface_area'),
                bedrooms      = data.get('bedrooms'),
                bathrooms     = data.get('bathrooms'),
                city          = data.get('city'),
                property_type = data.get('property_type'),
                source        = data.get('source', 'coinafrique'),
                latitude      = data.get('latitude'),
                longitude     = data.get('longitude'),
            )
            return Response(result)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=503)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class ModelResultsView(APIView):
    """
    Retourne les métriques du modèle ML (R², MAE, RMSE, MAPE).
    GET /api/properties/ml/results/
    """
    def get(self, request):
        import json, os
        results_path = os.path.join(os.path.dirname(__file__), 'ml', 'results.json')
        if not os.path.exists(results_path):
            return Response(
                {'error': 'Modèle non encore entraîné. Exécutez le Notebook 4.'},
                status=404
            )
        with open(results_path) as f:
            return Response(json.load(f))


# ── Gold Layer — indicateurs agrégés ─────────────────────────────────────────

class PrixMediansQuartierView(APIView):
    """
    Prix médians agrégés par quartier et type de bien (table Gold).
    GET /api/properties/gold/prix-medians/

    Query params :
        quartier  : filtrer par quartier (ex: ?quartier=Almadies)
        type_bien : filtrer par type de bien (ex: ?type_bien=Villa)
        min_obs   : nombre minimum d'observations (défaut : 5)
    """
    def get(self, request):
        qs        = PrixMedianQuartier.objects.all()
        quartier  = request.query_params.get('quartier')
        type_bien = request.query_params.get('type_bien')
        min_obs   = request.query_params.get('min_obs', 5)

        if quartier:  qs = qs.filter(quartier__icontains=quartier)
        if type_bien: qs = qs.filter(type_bien__icontains=type_bien)
        qs = qs.filter(nb_observations__gte=min_obs)

        data = list(qs.values(
            'quartier', 'type_bien', 'nb_observations',
            'prix_median', 'prix_m2_median',
            'prix_min', 'prix_max', 'ecart_type',
            'source', 'date_calcul',
        ))
        return Response({'count': len(data), 'results': data})


class TendancesMensuellesView(APIView):
    """
    Évolution mensuelle des prix par quartier (table Gold).
    GET /api/properties/gold/tendances/

    Query params :
        quartier  : filtrer par quartier
        type_bien : filtrer par type de bien
        annee     : filtrer par année (ex: ?annee=2026)
    """
    def get(self, request):
        qs        = TendanceMensuelle.objects.all()
        quartier  = request.query_params.get('quartier')
        type_bien = request.query_params.get('type_bien')
        annee     = request.query_params.get('annee')

        if quartier:  qs = qs.filter(quartier__icontains=quartier)
        if type_bien: qs = qs.filter(type_bien__icontains=type_bien)
        if annee:     qs = qs.filter(annee=annee)

        data = list(qs.values(
            'quartier', 'mois', 'annee',
            'prix_median', 'nb_annonces',
            'variation_pct', 'type_bien', 'source',
        ))
        return Response({'count': len(data), 'results': data})


class DashboardStatsView(APIView):
    """
    Tableau de bord consolidé — synthèse globale de la plateforme.
    GET /api/properties/gold/dashboard/

    Retourne :
        - Nombre total d'annonces et répartition par source
        - Top 10 quartiers les plus chers
        - Top 10 quartiers les plus abordables
        - Prix médian global par type de bien
    """
    def get(self, request):
        def safe_count(model):
            try: return model.objects.exclude(price__isnull=True).count()
            except: return 0

        sources = {
            'coinafrique': safe_count(CoinAfriqueProperty),
            'expat_dakar': safe_count(ExpatDakarProperty),
            'loger_dakar': safe_count(LogerDakarProperty),
            'dakarvente':  safe_count(DakarVenteProperty),
        }

        top_chers = list(
            PrixMedianQuartier.objects
            .filter(nb_observations__gte=5)
            .order_by('-prix_median')
            .values('quartier', 'type_bien', 'prix_median', 'nb_observations')[:10]
        )

        top_abordables = list(
            PrixMedianQuartier.objects
            .filter(nb_observations__gte=5, prix_median__gt=0)
            .order_by('prix_median')
            .values('quartier', 'type_bien', 'prix_median', 'nb_observations')[:10]
        )

        prix_par_type = list(
            PrixMedianQuartier.objects
            .values('type_bien')
            .annotate(
                prix_median_global = Avg('prix_median'),
                total_observations = Count('nb_observations'),
            )
            .order_by('-prix_median_global')
        )

        return Response({
            'total_annonces':           sum(sources.values()),
            'par_source':               sources,
            'top_quartiers_chers':      top_chers,
            'top_quartiers_abordables': top_abordables,
            'prix_par_type_bien':       prix_par_type,
        })
        