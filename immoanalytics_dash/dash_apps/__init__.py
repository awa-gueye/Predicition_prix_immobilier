"""
Enregistrement de tous les dashboards Dash avec django-plotly-dash.
Importé une seule fois depuis ImmoAnalyticsDashConfig.ready().
"""
from .main_dashboard      import register_main_dashboard
from .viewer_dashboard    import register_viewer_dashboard
from .analytics_dashboard import register_analytics_dashboard
from .admin_panel         import register_admin_panel

register_main_dashboard()
register_viewer_dashboard()
register_analytics_dashboard()
register_admin_panel()
