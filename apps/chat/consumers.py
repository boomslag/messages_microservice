import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import *
import jwt
from django.conf import settings
secret_key = settings.SECRET_KEY
import uuid
from .serializers import *
from django.db.models import F, Case, When


class InboxConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Get UserID
        self.user_id = self.scope['query_string'].decode('utf-8').split('=')[1]
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "inbox_%s" % self.room_name
        print(f'User {self.user_id} joined Websocket with Group name {self.room_group_name}')

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        if message_type == 'get_inboxes':
            # Fetch inboxes for user
            start = int(text_data_json.get('start', 0))
            count = int(text_data_json.get('count', 20))
            inboxes_data = await self.get_inboxes(start, count)
            # total_count = await self.get_inboxes_count()
            # Send inboxes to WebSocket
            await self.send_inboxes(inboxes_data)
        # Send message to room group
        else:
            message = text_data_json["message"]
            await self.channel_layer.group_send(
                self.room_group_name, {
                    "type": "chat_message", 
                    "message": message
                }
            )
    
    @database_sync_to_async
    def get_inboxes(self, start, count):
        chats = Chat.objects.filter(participants__uuid=self.user_id).order_by('-created_at').prefetch_related('participants')[start:start+count]
        serialized_chats = ChatSerializer(chats, many=True).data
        serialized_chats = self._add_participants_to_serialized_chats(serialized_chats)
        return serialized_chats

    def _add_participants_to_serialized_chats(self, serialized_chats):
        user_ids = set()
        for chat in serialized_chats:
            for participant in chat['participants']:
                user_ids.add(participant['uuid'])
        
        users = User.objects.filter(uuid__in=user_ids)
        user_map = {user.uuid: user for user in users}
        
        for chat in serialized_chats:
            chat['participants'] = [UserSerializer(user_map[participant['uuid']]).data for participant in chat['participants']]
        
        return serialized_chats
    
    @database_sync_to_async
    def get_inboxes_count(self):
        return Chat.objects.filter(participants__uuid=self.user_id).count()

    async def send_inboxes(self, inboxes_data):
        total_count = await self.get_inboxes_count()
        message = {
            'type': 'user_inboxes',
            'data': inboxes_data,
            'total_count': total_count
        }
        await self.send(text_data=json.dumps(message))

    async def send_inboxes_from_view(self, inboxes_data):
        total_count = await self.get_inboxes_count()
        message = {
            'type': 'user_inboxes_from_view',
            'data': inboxes_data,
            'total_count': total_count
        }
        await self.send(text_data=json.dumps(message))
    
    async def chat_message(self, event):
        chat = event['data']
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'data': chat,
        }))
    
    async def send_message(self, event):
        message = event['message']
        # send message to websocket
        await self.send(text_data=json.dumps({'message':message}))


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Get UserID
        self.user_id = self.scope['query_string'].decode('utf-8').split('=')[1]

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "chat_%s" % self.room_name

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # await self.set_user_chatroom_status(True)

        await self.accept()

    async def disconnect(self, close_code):
        # # Leave room group
        # await self.remove_user_from_stream()
        # await self.set_user_chatroom_status(False)

        # participants = await self.get_online_participants()
        # await self.send_online_participants(participants)
        print("Disconnect method called")

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Close the WebSocket connection
        await self.close()

    @database_sync_to_async
    def set_user_chatroom_status(self, status):
        user = User.objects.get(uuid=self.user_id)
        chat = Chat.objects.get(room_name=self.room_name, room_group_name=self.room_group_name)

        # Add or remove user from the connected_users field of the chat
        if status:
            chat.connected_users.add(user)
        else:
            chat.connected_users.remove(user)

        # Update the is_online status of the user in the chat
        user.is_online = status
        user.save()

        return status

    async def broadcast_user_status(self, user_id, is_online):
        # Broadcast updated user status to other participants in chat
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': user_id,
                'is_online': is_online,
            }
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        # print(text_data_json)
        if message_type == 'user_connected':
            # Fetch inboxes for user
            participants = await self.get_online_participants()
            await self.send_online_participants(participants)
            await self.forward_chat_info()
            
        elif message_type == 'user_disconnected':
            # Fetch inboxes for user
            participants = await self.get_online_participants()
            await self.send_online_participants(participants)
            await self.forward_chat_info()

        elif message_type == 'user_joined_video_room':
            # Update user's call status and add them to the stream
            await self.add_user_to_stream()
            await self.forward_chat_info()

            participants = await self.get_online_participants()
            await self.send_online_participants(participants)

        elif message_type == 'user_left_video_room':
            # Update user's call status and remove them from the stream
            await self.remove_user_from_stream()
            await self.forward_chat_info()

            participants = await self.get_online_participants()
            await self.send_online_participants(participants)
            await self.send_chat_data(participants)

        elif message_type == 'video_call_started':
            await self.add_user_to_stream()
            chat = await self.get_chat_by_room_name()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'video_call_started',
                    'user_id': text_data_json['user_id'],
                    "chat": await self.get_chat_serialized_data(chat),
                }
            )

        elif message_type == 'leave_video_call':
            await self.remove_user_from_stream()
            chat = await self.get_chat_by_room_name()
            participants_left = await self.get_online_participants()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'video_call_ended',
                    'user_id': text_data_json['user_id'],
                    'participants_left': participants_left,
                    "chat": await self.get_chat_serialized_data(chat),
                }
            )

        else:
            message = text_data_json["message"]
            await self.channel_layer.group_send(
                self.room_group_name, {
                    "type": "chat_message", 
                    "message": message,
                }
            )

    @database_sync_to_async
    def get_chat_serialized_data(self, chat):
        return ChatSerializer(chat).data

    @database_sync_to_async
    def get_chat_by_room_name(self):
        return Chat.objects.get(room_name=self.room_name)
    
    @database_sync_to_async
    def get_active_streams_count(self, chat):
        return chat.stream.filter(is_active=True).count()

    @database_sync_to_async
    def add_user_to_stream(self):
        user = User.objects.get(uuid=self.user_id)
        user.is_in_call = True
        user.save()
        
        chat = Chat.objects.get(room_name=self.room_name)
        stream, _ = Stream.objects.get_or_create(user=user, is_active=True)
        chat.stream.add(stream)
        # chat.connected_users.add(user)
        chat.save()

    @database_sync_to_async
    def remove_user_from_stream(self):
        user = User.objects.get(uuid=self.user_id)
        user.is_in_call = False
        user.save()

        chat = Chat.objects.get(room_name=self.room_name)
        stream = chat.stream.filter(user=user, is_active=True).first()
        if stream:
            chat.stream.remove(stream)
            # chat.connected_users.remove(user)
            chat.save()
            stream.is_active = False
            stream.save()
    
    @database_sync_to_async
    def get_online_participants(self):
        chat = Chat.objects.get(room_name=self.room_name, room_group_name=self.room_group_name)
        online_users = User.objects.filter(connected_chats=chat, is_online=True)

        # Use the UserSerializer to serialize the online_users queryset
        serializer = UserSerializer(online_users, many=True)
        participants = serializer.data
        return participants
    
    async def send_online_participants(self, participants):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'online_participants',
                'participants': participants,
            }
        )

    async def send_chat_data(self, participants_left):
        chat = await self.get_chat_by_room_name()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'video_call_ended',
                'user_id': self.user_id,
                'participants_left': participants_left,
                'chat': await self.get_chat_serialized_data(chat)
            }
        )

    async def online_participants(self, event):
        participants = event['participants']
        await self.send(text_data=json.dumps({
            'type': 'online_participants',
            'participants': participants,
        }))
    
    @database_sync_to_async
    def get_inboxes(self, start, count):
        chats = Chat.objects.filter(participants__uuid=self.user_id).order_by('-created_at').prefetch_related('participants')[start:start+count]
        serialized_chats = ChatSerializer(chats, many=True).data
        serialized_chats = self._add_participants_to_serialized_chats(serialized_chats)
        return serialized_chats

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))
    
    async def send_poll_vote(self, event):
        message = event['message']
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'poll_vote',
            'message': message
        }))

    async def user_status(self, event):
        user_id = event["user_id"]
        is_online = event["is_online"]
        print(f"User {user_id} is {'online' if is_online else 'offline'}")

    async def forward_chat_info(self):
        chat = await self.get_chat_by_room_name()
        active_streams_count = await self.get_active_streams_count(chat)
        # Send the number of active streams to the user
        await self.send(json.dumps({
            "type": "active_streams", 
            "count": active_streams_count,
            "chat": await self.get_chat_serialized_data(chat),
        }))

    async def video_call_started(self, event):
        user_id = event["user_id"]
        chat = event["chat"]

        # Send the video call started status to the WebSocket
        await self.send(text_data=json.dumps({
            "type": "video_call_started",
            "user_id": user_id,
            "chat": chat
        }))
    

    async def video_call_ended(self, event):
        user_id = event["user_id"]
        chat = event["chat"]
        participants_left = event["participants_left"]

        # Send the video call ended status to the WebSocket
        await self.send(text_data=json.dumps({
            "type": "video_call_ended",
            "user_id": user_id,
            "participants_left": participants_left,
            "chat": chat
        }))




class VideoCallConsumer(AsyncWebsocketConsumer):
    users_in_call = set()
    async def connect(self):
        # Get UserID
        token = self.scope["query_string"].decode().split("=")[1]
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            self.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            # Handle expired token error
            await self.close()
        except jwt.DecodeError:
            # Handle invalid token error
            await self.close()
        except Exception:
            # Handle other errors
            await self.close()

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "call_%s" % self.room_name

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        print(f'User {self.user_id} connected to Video Call Channel with Room name: {self.room_name}')

        # Add user to users_in_call and broadcast updated list
        VideoCallConsumer.users_in_call.add(self.user_id)
        await self.broadcast_users_list()

        await self.accept()
    
    async def disconnect(self, close_code):
        print(f'User {self.user_id} DISCONNECTED from Video Call Channel with Room name: {self.room_name}')

        # Remove user from users_in_call and broadcast updated list
        VideoCallConsumer.users_in_call.discard(self.user_id)
        await self.broadcast_users_list()

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Handle incoming WebSocket messages
    async def receive(self, text_data):
        message = json.loads(text_data)
        message_type = message["type"]
        if message_type == "offer":
            await self.send_offer(message)
        elif message_type == "answer":
            await self.send_answer(message)
        elif message_type == "ice_candidate":
            await self.send_ice_candidate(message)
        else:
            print(f"Unhandled message: {message}")

    async def send_offer(self, message):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "forward_offer",
                "offer": message["offer"],
                "from_user_id": self.user_id,
            },
        )

    async def send_answer(self, message):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "forward_answer",
                "answer": message["answer"],
                "from_user_id": self.user_id,
                "to_user_id": message["to_user_id"],
            },
        )

    async def send_ice_candidate(self, message):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "forward_ice_candidate",
                "candidate": message["candidate"],
                "from_user_id": self.user_id,
            },
        )

    async def broadcast_users_list(self):
        users_list = list(VideoCallConsumer.users_in_call)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "forward_users_list",
                "users": users_list,
            },
        )
    
    # These handlers will forward the messages to the respective clients
    async def forward_offer(self, event):
        await self.send(json.dumps({"type": "offer", "offer": event["offer"], "from_user_id": event["from_user_id"]}))

    async def forward_answer(self, event):
        await self.send(json.dumps({"type": "answer", "answer": event["answer"], "from_user_id": event["from_user_id"], "to_user_id": event["to_user_id"]}))

    async def forward_ice_candidate(self, event):
        await self.send(json.dumps({"type": "ice_candidate", "candidate": event["candidate"], "from_user_id": event["from_user_id"]}))
    
    async def forward_users_list(self, event):
        await self.send(json.dumps({"type": "update_users_list", "users": event["users"]}))