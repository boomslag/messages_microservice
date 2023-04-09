from django.urls import re_path

from .consumers import LiveRoomConsumer

websocket_urlpatterns = [
    re_path(r'^ws/room/(?P<room_name>[^/]+)/$', LiveRoomConsumer),
]