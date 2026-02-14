from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # ── Widget snippet ──────────────────────────────────────────────────────
    path('widget/', views.chat_widget, name='widget'),

    # ── Customer-facing API (called by widget.html) ─────────────────────────
    # POST: create new conversation
    path('start/', views.start_chat, name='start_chat'),

    # POST: send a message to an existing conversation
    path('conversation/<str:conversation_id>/send/', views.send_message, name='send_message'),

    # GET:  poll for new messages
    path('conversation/<str:conversation_id>/messages/', views.get_messages, name='get_messages'),

    # POST: submit a star rating
    path('conversation/<str:conversation_id>/rate/', views.rate_conversation, name='rate_conversation'),

    # ── Agent / Staff views (called by admin panel) ─────────────────────────
    path('agent/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/conversation/<str:conversation_id>/', views.agent_conversation, name='agent_conversation'),

    # POST: assign conversation to the logged-in agent
    path('agent/conversation/<str:conversation_id>/assign/', views.assign_conversation, name='assign_conversation'),

    # POST: change conversation status  (open / in_progress / resolved / closed …)
    path('agent/conversation/<str:conversation_id>/status/', views.update_status, name='update_status'),

    # POST: change conversation priority (low / medium / high / urgent)
    path('agent/conversation/<str:conversation_id>/priority/', views.update_priority, name='update_priority'),

    # POST: agent sets their own online/away/busy/offline status
    path('agent/status/', views.agent_status_update, name='agent_status'),

    # GET:  fetch a quick-reply template text + increment its usage counter
    path('agent/quick-reply/<int:reply_id>/', views.get_quick_reply, name='quick_reply'),
]