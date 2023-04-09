import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class LiveRoomConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        # Get UserID
        self.user_id = self.scope['query_string'].decode('utf-8').split('=')[1]

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "chat_%s" % self.room_name

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat_message", "message": message}
        )
    
    async def send_message(self, event):
        message = event['message']
        # send message to websocket
        await self.send(text_data=json.dumps({'message':message}))