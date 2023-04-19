from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, serializers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models.query_utils import Q
from django.db.models import F
from rest_framework_api.views import StandardAPIView
from django.shortcuts import get_object_or_404
import base64
import binascii
import bleach
from core.producer import producer
from .serializers import *
import uuid
import requests
import json
import jwt
from django.conf import settings
secret_key = settings.SECRET_KEY
from .models import *
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def validate_token(request):
    token = request.META.get('HTTP_AUTHORIZATION').split()[1]

    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return Response({"error": "Token has expired."}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.DecodeError:
        return Response({"error": "Token is invalid."}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        return Response({"error": "An error occurred while decoding the token."}, status=status.HTTP_401_UNAUTHORIZED)

    return payload


ALLOWED_TAGS = [    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'hr', 'i', 'li', 'ol', 'p', 'pre', 'span', 'strong', 'ul']
ALLOWED_ATTRIBUTES = {
    '*': ['style', 'class'],
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
}

def process_message(message):
    try:
        # Attempt to decode the message using base64
        decoded_message = binascii.a2b_base64(message)
        # If decoding was successful, assume it's already encrypted and return it as is.
        return message
    except binascii.Error:
        # If decoding failed, sanitize the message with Bleach.
        return bleach.clean(
            message,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
        )




class StartConversationView(StandardAPIView):
    permission_classes = (permissions.AllowAny,)

    def get_inboxes(self, user_id, start=0, count=20):
        chats = Chat.objects.filter(participants__uuid=user_id).order_by('-created_at').prefetch_related('participants')[start:start+count]
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

    def post(self, request, format=None):
        payload = validate_token(request)
        data = self.request.data
        uuid_str = str(uuid.uuid4())

        # Participants
        to_user = str(data['to_user'])
        to_user_username = str(data['to_user_username'])

        from_user = str(payload['user_id'])
        from_user_username = str(data['from_user_username'])

        # Check if a chat already exists between the two users
        chats = Chat.objects.filter(participants__uuid=from_user).filter(participants__uuid=to_user)
        if chats.exists():
            chat = chats.first()
        else:
            # Room and group name
            name = 'conversation'
            room_name = uuid_str
            room_group_name = f'chat_{room_name}'

            # Get or create users with provided uuid and update username if necessary
            from_user_obj, created = User.objects.get_or_create(uuid=from_user)
            if not created and from_user_obj.username != from_user_username:
                from_user_obj.username = from_user_username
                from_user_obj.save()

            to_user_obj, created = User.objects.get_or_create(uuid=to_user)
            if not created and to_user_obj.username != to_user_username:
                to_user_obj.username = to_user_username
                to_user_obj.save()

            chat, created = Chat.objects.get_or_create(
                name=name,
                room_name=room_name,
                room_group_name=room_group_name
            )
            chat.participants.add(from_user_obj, to_user_obj)

        # Get channel layer and group names
        channel_layer = get_channel_layer()
        # Send inboxes to WebSocket group for TO USER
        group_name_to_user = f'inbox_{to_user}'
        to_user_inboxes = self.get_inboxes(to_user)
        async_to_sync(channel_layer.group_send)(group_name_to_user, {
            'type': 'send_inboxes_from_view',
            'data': to_user_inboxes,
        })
        
        group_name_from_user = f'inbox_{from_user}'
        from_user_inboxes = self.get_inboxes(from_user)
        async_to_sync(channel_layer.group_send)(group_name_from_user, {
            'type': 'send_inboxes_from_view',
            'data': from_user_inboxes,
        })

        return self.send_response(ChatSerializer(chat).data, status=status.HTTP_201_CREATED)
    

class LoadConversationView(StandardAPIView):
    permission_classes = (permissions.AllowAny,)
    def get(self, request, room_name, room_group_name, *args, **kwargs):
        payload = validate_token(request)
        user_id = payload['user_id']
        chat = Chat.objects.get(room_name=room_name, room_group_name=room_group_name)
        participant_uuids = [p.uuid for p in chat.participants.all()]
        if user_id not in participant_uuids:
            return self.send_error("You do not have access to this chat", status=status.HTTP_403_FORBIDDEN)
        serializer = ChatSerializer(chat)

    
        return self.send_response(serializer.data, status=status.HTTP_200_OK)


class LoadMessagesView(StandardAPIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, room_name, room_group_name, *args, **kwargs):
        # Validate user's token and get user id
        payload = validate_token(request)
        user_id = payload['user_id']

        # Get the chat object for the given room name and room group name
        try:
            chat = Chat.objects.get(room_name=room_name, room_group_name=room_group_name)
        except Chat.DoesNotExist:
            return self.send_error("Chat not found", status=status.HTTP_404_NOT_FOUND)

        # Check if the user is a participant of the chat
        if not chat.participants.filter(uuid=user_id).exists():
            return self.send_error("You do not have access to this chat", status=status.HTTP_403_FORBIDDEN)

        # Get the latest 20 messages of the chat and serialize them
        messages = chat.messages.order_by('-timestamp')[:20][::-1]
        
        serializer = MessageSerializer(messages, many=True)

        # Return the serialized messages
        return self.paginate_response(request, serializer.data)
    

class SendMessageView(StandardAPIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request, format=None):
        payload = validate_token(request)
        user_id = payload['user_id']
        sender = get_object_or_404(User, uuid=user_id)
        # Get the chat object based on room name and group name
        room_name = request.data.get('roomName')
        room_group_name = request.data.get('roomGroupName')
        try:
            chat = get_object_or_404(Chat, room_name=room_name, room_group_name=room_group_name)
        except Chat.DoesNotExist:
            return Response({'error': 'Chat not found'}, status=status.HTTP_404_NOT_FOUND)

        # Create the message object
        message_content = request.data.get('message')
        message_content = process_message(message_content)

        message_mood = request.data.get('mood', None)
        message_public_key = request.FILES.get('publicKey', None)
        encryption = request.data.get('encryption', None)

        # print(request.data)

        if message_public_key:
            message = Message.objects.create(
                chat=chat,
                sender=sender,
                content=message_content if message_content.strip() != '<p><br></p>' else None,
                mood=message_mood,
                encryption=encryption,
            )
            # Create public key file object and attach it to message
            file_obj = File.objects.create(
                name=message_public_key.name,
                size=message_public_key.size,
                mime_type=message_public_key.content_type,
                file=message_public_key,
                message=message,  # Set the message field to the current Message object
            )
            message.public_key = file_obj
        else:
            message = Message.objects.create(
                chat=chat,
                sender=sender,
                content=message_content if message_content.strip() != '<p><br></p>' else None,
                mood=message_mood,
                public_key=None,
            )

        if 'voice_message' in request.FILES:
            voice_message = request.FILES['voice_message']
            message.voice_message = voice_message
            message.save()

        # Create the poll object if the poll data was included in the request
        poll_data = request.data.get('poll')
        if poll_data == 'null':
            poll_data = None
        if poll_data:
            poll_data = json.loads(poll_data)
            poll_question = poll_data.get('question')
            poll = Poll.objects.create(question=poll_question)
            poll_options = poll_data.get('options')
            if poll_options:
                for option in poll_options:
                    option_obj = PollOption.objects.create(option=option)
                    poll.options.add(option_obj)
            message.poll = poll
            message.save()

        # Add the files to the message
        files = request.FILES.getlist('files')
        if files:
            for file in files:
                file_obj = File.objects.create(
                    name=file.name,
                    size=file.size,
                    mime_type=file.content_type,
                    file=file,
                    message=message,  # Associate the file with the current Message object
                )

        # Parse the GIF data from the request and create a new GIF object
        gif_data = request.data.get('gif')
        if gif_data and gif_data != 'null':
            gif_data = json.loads(gif_data)
            gif = GIF.objects.create(
                url=gif_data['url'],
                title=gif_data.get('title', None),
                slug=gif_data.get('slug', None),
                embed_url=gif_data.get('embed_url', None),
                source=gif_data.get('source', None),
                rating=gif_data.get('rating', None)
            )
            message.gif=gif
            message.save()

        # Notify ChatGroup and send message to group
        channel_layer = get_channel_layer()

        # Send message to WebSocket group for TO USER
        group_name_to_user = f'chat_{str(chat.room_name)}'
        async_to_sync(channel_layer.group_send)(group_name_to_user, {
            'type': 'chat_message',
            'message': MessageSerializer(message).data,
        })

        return self.send_response('Test', status=status.HTTP_200_OK)
    


class VotePollView(StandardAPIView):
    permission_classes = (permissions.AllowAny,)
    def post(self, request, format=None):
        payload = validate_token(request)
        user_id = payload['user_id']
        user = get_object_or_404(User, uuid=user_id)
        chat = get_object_or_404(Chat, id=request.data.get('chat'))
        poll = get_object_or_404(Poll, id=request.data.get('poll'))

        if poll.voters.filter(uuid=user_id).exists():
            return self.send_error("You have already voted in this poll", status=status.HTTP_400_BAD_REQUEST)

        selected_option_id = request.data.get('option')
        poll_option = get_object_or_404(PollOption, id=selected_option_id)

        # Create a new PollVote object
        poll_vote = PollVote.objects.create(
            voter=user,
        )

        poll_option.votes.add(poll_vote)
        poll.voters.add(user)

        # Serialize the poll data and return it in the response
        serializer = PollSerializer(poll)

        message = get_object_or_404(Message, poll=poll)
        # Notify ChatGroup and send message to group
        channel_layer = get_channel_layer()

        # Send message to WebSocket group for TO USER
        group_name_to_user = f'chat_{str(chat.room_name)}'
        async_to_sync(channel_layer.group_send)(group_name_to_user, {
            'type': 'send_poll_vote',
            'message': MessageSerializer(message).data,
        })

        return self.send_response(serializer.data, status=status.HTTP_200_OK)