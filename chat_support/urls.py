from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Customer URLs
    path('', views.start_chat, name='start_chat'),
    path('widget/', views.chat_widget, name='widget'),
    path('conversation/<str:conversation_id>/', views.chat_conversation, name='conversation'),
    path('conversation/<str:conversation_id>/send/', views.send_message, name='send_message'),
    path('conversation/<str:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('conversation/<str:conversation_id>/rate/', views.rate_conversation, name='rate_conversation'),
    path('offline/', views.offline_message, name='offline_message'),
    
    # Agent URLs
    path('agent/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/conversation/<str:conversation_id>/', views.agent_conversation, name='agent_conversation'),
    path('agent/conversation/<str:conversation_id>/assign/', views.assign_conversation, name='assign_conversation'),
    path('agent/conversation/<str:conversation_id>/status/', views.update_status, name='update_status'),
    path('agent/conversation/<str:conversation_id>/priority/', views.update_priority, name='update_priority'),
    path('agent/status/', views.agent_status_update, name='agent_status'),
    path('agent/quick-reply/<int:reply_id>/', views.get_quick_reply, name='get_quick_reply'),
]