"""
urls_dash.py — Documentation uniquement.
Les pages des dashboards sont déclarées directement dans
immobilier_project/urls.py via les vues importées :

    path('dashboard/',  dashboard_page,   name='dashboard'),
    path('analytics/',  analytics_page,   name='analytics'),
    path('viewer/',     viewer_page,       name='viewer'),
    path('map/',        map_page,          name='map'),
    path('immo-admin/', admin_panel_page,  name='immo_admin'),

Chaque vue renvoie un template Django qui embarque l'app Dash correspondante
via le tag : {% plotly_app name="MainDashboard" %}
"""
