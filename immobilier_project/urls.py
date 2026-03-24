"""
ImmoPredict SN — urls.py
Routes complètes avec toutes les nouvelles pages.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect

from immoanalytics_dash.views import (
    login_view, logout_view, register_view,
    profile_view, settings_view,
    viewer_page, map_page, estimation_page,
    admin_panel_page,
    api_current_user, api_check_auth,
    about_view, contact_view,
)
from immoanalytics_dash.chart_views import (
    dashboard_page, analytics_page, api_stats_real,
)
from immoanalytics_dash.chatbot_groq import api_chatbot


def index_view(request):
    if request.user.is_authenticated:
        from immoanalytics_dash.views import get_user_redirect
        return redirect(get_user_redirect(request.user))
    return TemplateView.as_view(template_name='immoanalytics/welcome.html')(request)


urlpatterns = [
    # ── Accueil ───────────────────────────────────────────────────────────────
    path('', index_view, name='index'),

    # ── Django Admin ──────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── API REST propriétés ───────────────────────────────────────────────────
    path('api/properties/', include('properties.urls')),
    path('api/stats/',      api_stats_real, name='api_stats_real'),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('immo/login/',    login_view,    name='immo_login'),
    path('immo/logout/',   logout_view,   name='immo_logout'),
    path('immo/register/', register_view, name='immo_register'),
    path('immo/profile/',  profile_view,  name='immo_profile'),
    path('immo/settings/', settings_view, name='immo_settings'),

    # ── API internes ──────────────────────────────────────────────────────────
    path('immo/api/me/',      api_current_user, name='immo_api_me'),
    path('immo/api/check/',   api_check_auth,   name='immo_api_check'),
    path('immo/api/chatbot/', api_chatbot,       name='immo_api_chatbot'),

    # ── Dash (admin panel seulement) ──────────────────────────────────────────
    path('dpd/', include('django_plotly_dash.urls')),

    # ── Pages principales ─────────────────────────────────────────────────────
    path('dashboard/',   dashboard_page,  name='dashboard'),
    path('analytics/',   analytics_page,  name='analytics'),
    path('viewer/',      viewer_page,     name='viewer'),
    path('map/',         map_page,        name='map'),
    path('estimation/',  estimation_page, name='estimation'),
    path('immo-admin/',  admin_panel_page, name='immo_admin'),

    # ── Pages informatives ────────────────────────────────────────────────────
    path('about/',   about_view,   name='about'),
    path('contact/', contact_view, name='contact'),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
