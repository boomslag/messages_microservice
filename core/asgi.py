import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
from django.core.asgi import get_asgi_application
django_asgi_app=get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

import apps.chat.routing as ChatRouting
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            ChatRouting.websocket_urlpatterns
        )
    ),
    "websocket_timeout": 60,  # Increase this value as needed
})