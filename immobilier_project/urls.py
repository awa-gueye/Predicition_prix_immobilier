"""immobilier_project/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from immoanalytics_dash import views as auth_views
from immoanalytics_dash import chart_views

# Chatbot : essaie Gemini d'abord, puis Groq, puis None
api_chatbot = None
try:
    from immoanalytics_dash.chatbot_gemini import api_chatbot
except ImportError:
    pass
if api_chatbot is None:
    try:
        from immoanalytics_dash.chatbot_groq import api_chatbot
    except ImportError:
        pass

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', auth_views.welcome_or_dashboard, name='home'),
    path('welcome/', auth_views.welcome_view, name='welcome'),
    path('dashboard/', chart_views.dashboard_page, name='dashboard'),
    path('immo/login/', auth_views.login_view, name='login'),
    path('immo/logout/', auth_views.logout_view, name='logout'),
    path('immo/register/', auth_views.register_view, name='register'),
    path('map/', auth_views.map_page, name='map'),
    path('estimation/', auth_views.estimation_page, name='estimation'),
    path('about/', auth_views.about_view, name='about'),
    path('contact/', auth_views.contact_view, name='contact'),
    path('immo-admin/', auth_views.admin_panel_page, name='dash_page'),
    path('', include('listings.urls')),
    path('api/properties/', include('properties.urls')),
    path('api/stats/', chart_views.api_stats_real, name='api_stats'),
    path('api/debug-db/', chart_views.api_debug_db, name='api_debug_db'),
]
if hasattr(auth_views, 'api_notifications'):
    urlpatterns += [path('api/notifications/', auth_views.api_notifications, name='api_notifications')]
if hasattr(chart_views, 'api_predict'):
    urlpatterns += [path('api/predict/', chart_views.api_predict, name='api_predict')]
if api_chatbot:
    urlpatterns += [path('immo/api/chatbot/', api_chatbot, name='immo_api_chatbot')]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
