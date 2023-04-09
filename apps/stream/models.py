from django.db import models

class User(models.Model):
    uuid = models.CharField(max_length=256, unique=True)
    username = models.CharField(max_length=256)
    rooms = models.ManyToManyField('Room', related_name='users')

class Room(models.Model):
    name = models.CharField(max_length=255)
    creator = models.CharField(max_length=256)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.ManyToManyField('User', related_name='rooms_participated')

class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    status = models.CharField(max_length=10, choices=[('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read')], default='sent')
    type = models.CharField(max_length=10, choices=[('text', 'Text'), ('image', 'Image'), ('video', 'Video'), ('audio', 'Audio')], default='text')

class File(models.Model):
    message = models.ForeignKey(Message, related_name='attachments', on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    size = models.IntegerField()
    mime_type = models.CharField(max_length=256)

class Reaction(models.Model):
    message = models.ForeignKey(Message, related_name='reactions', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reactions', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=[('like', 'Like'), ('love', 'Love'), ('angry', 'Angry'), ('wow', 'Wow')], default='like')

class Stream(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    creator = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(User, related_name='streams')
    messages = models.ManyToManyField(Message, blank=True, related_name='streams')
    participants = models.ManyToManyField(Room, related_name='streams')