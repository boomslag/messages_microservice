from rest_framework import serializers
from .models import *


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'uuid',
            'username',
            'is_chatbot',
            'is_online',
            'is_in_call',
        ]

class StreamSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = Stream
        fields = [
            'id',
            'user',
            'is_active',
        ]


class ChatSerializer(serializers.ModelSerializer):
    last_message = serializers.CharField(source='get_last_message')
    participants = UserSerializer(many=True)
    # connected_users = UserSerializer(many=True)
    stream = StreamSerializer(many=True)
    class Meta:
        model = Chat
        fields = [
            'id',
            'name',
            'participants',
            'last_message',
            'room_name',
            'room_group_name',
            # 'connected_users',
            'created_at',
            'stream',
        ]
    
class BreakoutRoomSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True)
    stream = StreamSerializer(many=True)
    # connected_users = UserSerializer(many=True)
    class Meta:
        model = BreakoutRoom
        fields = [
            'id',
            'name',
            'chat',
            'participants',
            'room_name',
            'room_group_name',
            'created_at',
            # 'connected_users',
            'stream',
        ]

class GIFSerializer(serializers.ModelSerializer):
    class Meta:
        model = GIF
        fields = ['id', 'url', 'title', 'slug', 'embed_url', 'source', 'rating']


class FileSerializer(serializers.ModelSerializer):
    message = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all())

    class Meta:
        model = File
        fields = ['id', 'message','file', 'name', 'size', 'mime_type', 'created_at']


class ReactionSerializer(serializers.ModelSerializer):
    message = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all())
    user = UserSerializer()

    class Meta:
        model = Reaction
        fields = ['id', 'message', 'user', 'type']


class PollOptionSerializer(serializers.ModelSerializer):
    votes_count=serializers.CharField()
    class Meta:
        model = PollOption
        fields = ('id', 'option', 'votes_count')


class PollSerializer(serializers.ModelSerializer):
    options = PollOptionSerializer(many=True)
    total_votes_count=serializers.CharField()
    voters=UserSerializer(many=True)
    class Meta:
        model = Poll
        fields = ('id', 'question', 'options', 'total_votes_count', 'voters')


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer()
    read_by = UserSerializer(many=True)
    files = FileSerializer(many=True)
    public_key = FileSerializer()
    gif = GIFSerializer()
    poll = PollSerializer()

    class Meta:
        model = Message
        fields = [
            'id',
            'chat',
            'sender',
            'content',
            'voice_message',
            'public_key',
            'timestamp',
            'read_by',
            'status',
            'mood',
            'type',
            'created_at',
            'files',
            'encryption',
            'gif',
            'poll',
        ]