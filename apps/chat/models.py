from django.db import models

class User(models.Model):
    uuid = models.CharField(max_length=256, unique=True)
    username = models.CharField(max_length=256, blank=True, null=True)
    is_online = models.BooleanField(default=False)
    is_in_call = models.BooleanField(default=False)
    is_chatbot = models.BooleanField(default=False)
    # add any other user-related fields as needed


class Stream(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stream_participant')
    is_active = models.BooleanField(default=True)
    # add any other stream-related fields as needed


class Chat(models.Model):
    name = models.CharField(max_length=256)
    participants = models.ManyToManyField(User, related_name='chats')
    room_name = models.CharField(max_length=255, blank=True, null=True)
    room_group_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    connected_users = models.ManyToManyField(User, blank=True, related_name='connected_chats')
    stream = models.ManyToManyField(Stream)

    def get_last_message(self):
        last_message = self.messages.order_by('-timestamp').first()
        return last_message.content if last_message else None


class BreakoutRoom(models.Model):
    name = models.CharField(max_length=256)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='breakout_rooms')
    participants = models.ManyToManyField(User, related_name='breakout_rooms')
    room_name = models.CharField(max_length=255, blank=True, null=True)
    room_group_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    connected_users = models.ManyToManyField(User, blank=True, related_name='connected_breakout_rooms')
    stream = models.ManyToManyField(Stream)


class Poll(models.Model):
    question = models.CharField(max_length=255)
    options = models.ManyToManyField('PollOption', related_name='poll_options')
    voters = models.ManyToManyField(User, related_name='poll_voters')

    def total_votes_count(self):
        total_votes = 0
        for option in self.options.all():
            total_votes += option.votes.count()
        return total_votes

class PollOption(models.Model):
    option = models.CharField(max_length=255)
    votes = models.ManyToManyField('PollVote', related_name='votes')

    def votes_count(self):
        return self.votes.count()

class PollVote(models.Model):
    voter = models.ForeignKey(User, related_name='poll_votes', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.voter} voted for {self.poll_option}'


class GIF(models.Model):
    # message = models.ForeignKey('Message', related_name='gif', on_delete=models.CASCADE)
    url = models.URLField()
    title = models.CharField(max_length=255, null=True, blank=True)
    slug = models.SlugField(max_length=255, null=True, blank=True)
    embed_url = models.URLField(null=True, blank=True)
    source = models.URLField(null=True, blank=True)
    rating = models.CharField(max_length=255, null=True, blank=True)


class Message(models.Model):

    mood_choices = (
        ('excited', 'Excited'),
        ('loved', 'Loved'),
        ('happy', 'Happy'),
        ('sad', 'Sad'),
        ('thumbsy', 'Thumbsy'),
        ('none', 'I feel nothing'),
    )
    
    encryption_choices = (
        ('lattice', 'LATTICE'),
        ('rsa', 'RSA'),
        ('none', 'None'),
    )

    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    content = models.TextField(null=True, blank=True)
    gif = models.ForeignKey(GIF, related_name='message_gif', on_delete=models.CASCADE,null=True, blank=True)
    poll = models.ForeignKey(Poll, related_name='message_poll', on_delete=models.CASCADE,null=True, blank=True)
    voice_message = models.FileField(null=True, blank=True)
    public_key = models.ForeignKey('File',null=True, blank=True, on_delete=models.CASCADE, related_name='message_public_key')
    timestamp = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    status = models.CharField(max_length=10, choices=[('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read')], default='sent')
    mood = models.CharField(max_length=10, choices=mood_choices, default='none')
    type = models.CharField(max_length=10, choices=[('text', 'Text'), ('image', 'Image'), ('video', 'Video'), ('audio', 'Audio')], default='text')
    encryption = models.CharField(max_length=30, choices=encryption_choices, default='none')
    created_at = models.DateTimeField(auto_now_add=True)


class File(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=255)
    file = models.FileField(upload_to='message_sent_files/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Reaction(models.Model):
    message = models.ForeignKey(Message, related_name='reactions', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reactions', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=[('like', 'Like'), ('love', 'Love'), ('angry', 'Angry'), ('wow', 'Wow')], default='like')


class Thread(models.Model):
    message = models.ForeignKey('Message', related_name='threads', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', related_name='replies', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['message__timestamp']

    def __str__(self):
        return f'Thread on {self.message}'


class Reply(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='replies')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='replies')
    content = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class Mention(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='mentions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentions')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'message')

    def __str__(self):
        return f'{self.user} mentioned in {self.message}'

