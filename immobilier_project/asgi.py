"""
ASGI config for immobilier_project project.
Mis à jour pour django-plotly-dash (WebSockets via Channels).
"""
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth    import AuthMiddlewareStack
from django.urls      import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_project.settings')
django.setup()

from django_plotly_dash.consumers import MessageConsumer

ws_patterns = [
    re_path(r'^dpd/ws/channel', MessageConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(ws_patterns)
    ),
})
