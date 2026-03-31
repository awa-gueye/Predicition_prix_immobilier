"""immobilier_project/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from immoanalytics_dash import views as auth_views
from immoanalytics_dash import chart_views

# Import chatbot (peut être dans views ou dans chatbot_groq)
try:
    from immoanalytics_dash.chatbot_groq import api_chatbot
except ImportError:
    api_chatbot = getattr(auth_views, 'api_chatbot', None)

urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),

    # Authentification
    path('immo/login/',    auth_views.login_view,    name='login'),
    path('immo/logout/',   auth_views.logout_view,   name='logout'),
    path('immo/register/', auth_views.register_view, name='register'),

    # Dashboard (analytics fusionnées — Analyses supprimé)
    path('',           chart_views.dashboard_page, name='dashboard'),
    path('dashboard/', chart_views.dashboard_page, name='dashboard_named'),

    # Pages principales
    path('map/',        auth_views.map_page,        name='map'),
    path('estimation/', auth_views.estimation_page, name='estimation'),
    path('about/',      auth_views.about_view,      name='about'),
    path('contact/',    auth_views.contact_view,    name='contact'),

    # Admin panel ImmoPredict
    path('immo-admin/', auth_views.admin_panel_page, name='dash_page'),

    # Vente, Location, Profil, Annonces vendeurs
    path('', include('listings.urls')),

    # API scraping
    path('api/properties/', include('properties.urls')),

    # API stats & debug
    path('api/stats/',    chart_views.api_stats_real, name='api_stats'),
    path('api/debug-db/', chart_views.api_debug_db,   name='api_debug_db'),
]

# Chatbot (optionnel)
if api_chatbot:
    urlpatterns += [
        path('immo/api/chatbot/', api_chatbot, name='immo_api_chatbot'),
    ]

# Fichiers media et static
urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)