"""immobilier_project/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from immoanalytics_dash import views as auth_views
from immoanalytics_dash import chart_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('immo/login/',    auth_views.login_view,    name='login'),
    path('immo/logout/',   auth_views.logout_view,   name='logout'),
    path('immo/register/', auth_views.register_view, name='register'),
    path('',           chart_views.dashboard_page, name='dashboard'),
    path('dashboard/', chart_views.dashboard_page, name='dashboard_named'),
    path('map/',        auth_views.map_page,        name='map'),
    path('estimation/', auth_views.estimation_page, name='estimation'),
    path('contact/',   auth_views.contact_view, name='contact'),
    path('about/',     auth_views.about_view,   name='about'),
    path('immo-admin/', auth_views.dash_page, name='dash_page'),
    path('', include('listings.urls')),
    path('api/properties/', include('properties.urls')),
    path('api/stats/',    chart_views.api_stats_real, name='api_stats'),
    path('api/debug-db/', chart_views.api_debug_db,   name='api_debug_db'),
    path('immo/api/chatbot/', include('immoanalytics_dash.chatbot_urls')),
]
urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
