import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import apps.chat.routing as ChatRouting
# import apps.stream.routing as RoomRouting

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            ChatRouting.websocket_urlpatterns
        )
    ),
})