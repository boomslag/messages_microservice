from django.urls import re_path

from .consumers import InboxConsumer, ChatConsumer, VideoCallConsumer

websocket_urlpatterns = [
    re_path(r'^ws/inbox/(?P<room_name>[^/]+)/$', InboxConsumer.as_asgi()),
    re_path(r'^ws/chat/(?P<room_name>[^/]+)/$', ChatConsumer.as_asgi()),
    re_path(r'^ws/call/(?P<room_name>[^/]+)/$', VideoCallConsumer.as_asgi()),
]