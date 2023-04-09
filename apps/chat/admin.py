from django.contrib import admin

# Register your models here.
from .models import *
admin.site.register(User)
admin.site.register(Chat)
admin.site.register(Message)
admin.site.register(Reaction)
admin.site.register(File)
admin.site.register(Poll)
admin.site.register(PollOption)
admin.site.register(PollVote)
admin.site.register(Mention)
admin.site.register(Thread)