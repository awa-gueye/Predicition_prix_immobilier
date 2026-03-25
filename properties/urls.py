from django.urls import path
from . import views

urlpatterns = [
    # ── CoinAfrique ───────────────────────────────────────────────────────────
    path('coinafrique/',          views.CoinAfriqueListView.as_view(),   name='coinafrique-list'),
    path('coinafrique/<str:pk>/', views.CoinAfriqueDetailView.as_view(), name='coinafrique-detail'),

    # ── Expat-Dakar ───────────────────────────────────────────────────────────
    path('expat-dakar/',          views.ExpatDakarListView.as_view(),    name='expat-dakar-list'),
    path('expat-dakar/<str:pk>/', views.ExpatDakarDetailView.as_view(),  name='expat-dakar-detail'),

    # ── Loger-Dakar ───────────────────────────────────────────────────────────
    path('loger-dakar/',          views.LogerDakarListView.as_view(),    name='loger-dakar-list'),
    path('loger-dakar/<str:pk>/', views.LogerDakarDetailView.as_view(),  name='loger-dakar-detail'),

    # ── DakarVente ────────────────────────────────────────────────────────────
    path('dakarvente/',          views.DakarVenteListView.as_view(),     name='dakarvente-list'),
    path('dakarvente/<str:pk>/', views.DakarVenteDetailView.as_view(),   name='dakarvente-detail'),


    # ── Vues agrégées ─────────────────────────────────────────────────────────
    path('all/',   views.AllPropertiesView.as_view(), name='all-properties'),
    path('stats/', views.StatsView.as_view(),         name='stats'),

    # ── Machine Learning ──────────────────────────────────────────────────────
    path('predict/',    views.PredictPriceView.as_view(), name='predict-price'),
    path('ml/results/', views.ModelResultsView.as_view(), name='ml-results'),

    # ── Gold Layer ────────────────────────────────────────────────────────────
    path('gold/prix-medians/', views.PrixMediansQuartierView.as_view(), name='gold-prix-medians'),
    path('gold/tendances/',    views.TendancesMensuellesView.as_view(),  name='gold-tendances'),
    path('gold/dashboard/',    views.DashboardStatsView.as_view(),       name='gold-dashboard'),
]