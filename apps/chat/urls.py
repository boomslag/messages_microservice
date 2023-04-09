from django.urls import path
from .views import *

app_name = "chat"

urlpatterns = [
    path('start_conversation/', StartConversationView.as_view()),
    path('send_message/', SendMessageView.as_view()),
    path('load_conversation/<str:room_name>/<str:room_group_name>/', LoadConversationView.as_view()),
    path('load_conversation_messages/<str:room_name>/<str:room_group_name>/', LoadMessagesView.as_view()),
    path('vote_poll/', VotePollView.as_view()),
]