from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Max
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    ChatConversation, ChatMessage,
    ChatQuickReply, ChatOfflineMessage, AgentStatus,
)
from django.db import models as dj_models    
from django.db.models import F        
from django.db import models
# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def get_client_ip(request):
    """Return the real client IP, honouring X-Forwarded-For."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def assign_to_agent(conversation):
    """
    Auto-assign conversation to the online agent with fewest active chats.
    Creates a system message on successful assignment.
    """
    agents = (
        AgentStatus.objects
        .filter(status='online')
        .order_by('active_conversations')
        .select_related('agent')
    )
    for agent_status in agents:
        if agent_status.is_available():
            conversation.assigned_to = agent_status.agent
            conversation.status = 'in_progress'
            conversation.save(update_fields=['assigned_to', 'status'])

            AgentStatus.objects.filter(pk=agent_status.pk).update(
                active_conversations=agent_status.active_conversations + 1
            )
            ChatMessage.objects.create(
                conversation=conversation,
                sender_name='System',
                message=f'You are connected with {agent_status.agent.get_full_name() or agent_status.agent.username}.',
                is_from_customer=False,
                message_type='system',
            )
            return True
    return False


# ──────────────────────────────────────────────
# CUSTOMER VIEWS
# ──────────────────────────────────────────────

def chat_widget(request):
    """Embeddable floating chat bubble (renders widget.html)."""
    is_online = AgentStatus.objects.filter(status='online').exists()
    return render(request, 'chat/widget.html', {'is_online': is_online})


def start_chat(request):
    """
    GET  → render the start-chat form.
    POST → create a conversation, optionally with a first message, then redirect.
    Supports both standard form submissions and AJAX.
    """
    if request.method != 'POST':
        return render(request, 'chat/start_chat.html')

    subject      = request.POST.get('subject', 'General Inquiry').strip() or 'General Inquiry'
    message_text = request.POST.get('message', '').strip()

    # Build conversation
    if request.user.is_authenticated:
        conv = ChatConversation.objects.create(
            user=request.user,
            subject=subject,
            ip_address=get_client_ip(request),
        )
    else:
        guest_name  = request.POST.get('guest_name', 'Guest').strip() or 'Guest'
        guest_email = request.POST.get('guest_email', '').strip()
        conv = ChatConversation.objects.create(
            guest_name=guest_name,
            guest_email=guest_email,
            subject=subject,
            ip_address=get_client_ip(request),
        )

    # First message
    if message_text:
        ChatMessage.objects.create(
            conversation=conv,
            sender=request.user if request.user.is_authenticated else None,
            sender_name=conv.get_display_name(),
            message=message_text,
            is_from_customer=True,
        )

    assign_to_agent(conv)

    if is_ajax(request):
        return JsonResponse({
            'success': True,
            'conversation_id': conv.conversation_id,
            'redirect_url': f'/chat/conversation/{conv.conversation_id}/',
        })

    return redirect('chat:conversation', conversation_id=conv.conversation_id)


def chat_conversation(request, conversation_id):
    """Customer-facing conversation page."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    # Mark all agent/system messages as read
    conversation.messages.filter(
        is_from_customer=False, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    messages = conversation.messages.all()

    return render(request, 'chat/conversation.html', {
        'conversation': conversation,
        'messages':     messages,
    })


@require_http_methods(['POST'])
def send_message(request, conversation_id):
    """
    POST /chat/conversation/<id>/send/
    Accepts JSON body or multipart/form-data.
    Returns JSON with the persisted message.
    """
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    message_text = request.POST.get('message', '').strip()
    attachment   = request.FILES.get('attachment')

    if not message_text and not attachment:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty.'}, status=400)

    is_staff = request.user.is_authenticated and request.user.is_staff

    # Determine message type
    if attachment:
        msg_type = 'image' if attachment.content_type.startswith('image/') else 'file'
    else:
        msg_type = 'text'

    msg = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user if request.user.is_authenticated else None,
        sender_name=(
            request.user.get_full_name() or request.user.username
            if is_staff
            else conversation.get_display_name()
        ),
        message=message_text,
        attachment=attachment,
        is_from_customer=not is_staff,
        message_type=msg_type,
    )

    # Reopen closed conversations when a customer writes again
    if not is_staff and conversation.status in ('resolved', 'closed'):
        conversation.status = 'open'
        conversation.save(update_fields=['status'])

    return JsonResponse({
        'success': True,
        'message': {
            'id':              msg.id,
            'message':         msg.message,
            'sender_name':     msg.sender_name,
            'is_from_customer': msg.is_from_customer,
            'message_type':    msg.message_type,
            'created_at':      msg.created_at.strftime('%H:%M'),
            'attachment_url':  msg.attachment.url if msg.attachment else None,
        },
    })


def get_messages(request, conversation_id):
    """
    GET /chat/conversation/<id>/messages/?last_message_id=<int>
    Long-polling endpoint. Returns messages with id > last_message_id.
    """
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    try:
        last_id = int(request.GET.get('last_message_id', 0))
    except ValueError:
        last_id = 0

    qs = conversation.messages.filter(id__gt=last_id)

    is_staff = request.user.is_authenticated and request.user.is_staff

    # Mark messages as read on the receiving side
    if not is_staff:
        qs.filter(is_from_customer=False, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
    else:
        qs.filter(is_from_customer=True, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

    msg_list = []
    for m in qs:
        msg_list.append({
            'id':               m.id,
            'message':          m.message,
            'sender_name':      m.sender_name or 'Guest',
            'is_from_customer': m.is_from_customer,
            'message_type':     m.message_type,
            'created_at':       m.created_at.strftime('%H:%M'),
            'attachment_url':   m.attachment.url if m.attachment else None,
        })

    return JsonResponse({'success': True, 'messages': msg_list})


@require_http_methods(['POST'])
def rate_conversation(request, conversation_id):
    """POST rating (1-5) and optional feedback text for a conversation."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    try:
        rating = int(request.POST.get('rating', 0))
        if not (1 <= rating <= 5):
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Rating must be 1–5.'}, status=400)

    conversation.rating   = rating
    conversation.feedback = request.POST.get('feedback', '').strip()
    conversation.save(update_fields=['rating', 'feedback'])

    return JsonResponse({'success': True})


def offline_message(request):
    """
    GET  → render offline contact form.
    POST → save the offline message and acknowledge.
    """
    if request.method != 'POST':
        return render(request, 'chat/offline_form.html')

    required = ['name', 'email', 'subject', 'message']
    missing  = [f for f in required if not request.POST.get(f, '').strip()]
    if missing:
        if is_ajax(request):
            return JsonResponse(
                {'success': False, 'error': f"Missing fields: {', '.join(missing)}"},
                status=400,
            )
        return render(request, 'chat/offline_form.html', {'error': 'Please fill in all fields.'})

    ChatOfflineMessage.objects.create(
        name=request.POST['name'].strip(),
        email=request.POST['email'].strip(),
        subject=request.POST['subject'].strip(),
        message=request.POST['message'].strip(),
        ip_address=get_client_ip(request),
    )

    if is_ajax(request):
        return JsonResponse({
            'success': True,
            'message': "Message received! We'll get back to you within 24 hours.",
        })

    return redirect('chat:start_chat')


# ──────────────────────────────────────────────
# AGENT VIEWS
# ──────────────────────────────────────────────

@staff_member_required
def agent_dashboard(request):
    """Main agent dashboard with filters, pagination, and live stats."""
    conversations = (
        ChatConversation.objects
        .select_related('user', 'assigned_to')
        .annotate(
            message_count=Count('messages'),
            last_message_time=Max('messages__created_at'),
        )
    )

    # ── Filters ──────────────────────────────────
    status_filter = request.GET.get('status')
    if status_filter:
        conversations = conversations.filter(status=status_filter)

    assigned_filter = request.GET.get('assigned_to')
    if assigned_filter == 'me':
        conversations = conversations.filter(assigned_to=request.user)
    elif assigned_filter == 'unassigned':
        conversations = conversations.filter(assigned_to__isnull=True)

    priority_filter = request.GET.get('priority')
    if priority_filter:
        conversations = conversations.filter(priority=priority_filter)

    search_q = request.GET.get('q', '').strip()
    if search_q:
        conversations = conversations.filter(
            conversation_id__icontains=search_q
        ) | conversations.filter(
            subject__icontains=search_q
        ) | conversations.filter(
            guest_name__icontains=search_q
        ) | conversations.filter(
            guest_email__icontains=search_q
        )

    conversations = conversations.order_by('-created_at')

    # ── Pagination ────────────────────────────────
    paginator = Paginator(conversations, 20)
    page      = paginator.get_page(request.GET.get('page', 1))

    # ── Stats ─────────────────────────────────────
    base = ChatConversation.objects
    stats = {
        'total':       base.count(),
        'open':        base.filter(status='open').count(),
        'in_progress': base.filter(status='in_progress').count(),
        'my_active':   base.filter(
            assigned_to=request.user, status__in=['open', 'in_progress']
        ).count(),
        'unassigned':  base.filter(assigned_to__isnull=True).count(),
        'resolved_today': base.filter(
            status='resolved',
            closed_at__date=timezone.now().date()
        ).count(),
    }

    # ── Agent status ──────────────────────────────
    my_status, _ = AgentStatus.objects.get_or_create(agent=request.user)

    return render(request, 'chat/agent_dashboard.html', {
        'conversations': page,
        'stats':         stats,
        'my_status':     my_status,
    })


@staff_member_required
def agent_conversation(request, conversation_id):
    """Agent conversation detail page."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    # Mark all customer messages as read
    conversation.messages.filter(
        is_from_customer=True, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    messages      = conversation.messages.all()
    quick_replies = ChatQuickReply.objects.filter(is_active=True)[:15]

    return render(request, 'chat/agent_conversation.html', {
        'conversation': conversation,
        'messages':     messages,
        'quick_replies': quick_replies,
    })


@staff_member_required
@require_http_methods(['POST'])
def assign_conversation(request, conversation_id):
    """Assign a conversation to the requesting agent (or another via POST body)."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    assign_user = request.user  # default: self-assign
    conversation.assigned_to = assign_user
    if conversation.status == 'open':
        conversation.status = 'in_progress'
    conversation.save(update_fields=['assigned_to', 'status'])

    ChatMessage.objects.create(
        conversation=conversation,
        sender_name='System',
        message=f'Conversation assigned to {assign_user.get_full_name() or assign_user.username}.',
        is_from_customer=False,
        message_type='system',
    )

    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(['POST'])
def update_status(request, conversation_id):
    """Update conversation status (open / in_progress / waiting / resolved / closed)."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    new_status = request.POST.get('status', '').strip()
    valid      = [c[0] for c in ChatConversation.STATUS_CHOICES]
    if new_status not in valid:
        return JsonResponse({'success': False, 'error': 'Invalid status.'}, status=400)

    conversation.status = new_status
    if new_status in ('resolved', 'closed'):
        conversation.closed_at = timezone.now()
        # Decrement agent counter
        if conversation.assigned_to:
            AgentStatus.objects.filter(
                agent=conversation.assigned_to,
                active_conversations__gt=0
            ).update(active_conversations=models.F('active_conversations') - 1)

    conversation.save(update_fields=['status', 'closed_at'])

    ChatMessage.objects.create(
        conversation=conversation,
        sender_name='System',
        message=f'Status changed to {conversation.get_status_display()}.',
        is_from_customer=False,
        message_type='system',
    )

    return JsonResponse({'success': True, 'status': conversation.get_status_display()})


@staff_member_required
@require_http_methods(['POST'])
def update_priority(request, conversation_id):
    """Update conversation priority."""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    new_priority = request.POST.get('priority', '').strip()
    valid        = [c[0] for c in ChatConversation.PRIORITY_CHOICES]
    if new_priority not in valid:
        return JsonResponse({'success': False, 'error': 'Invalid priority.'}, status=400)

    conversation.priority = new_priority
    conversation.save(update_fields=['priority'])

    return JsonResponse({'success': True, 'priority': conversation.get_priority_display()})


@staff_member_required
@require_http_methods(['POST'])
def agent_status_update(request):
    """Toggle the current agent's availability status."""
    new_status = request.POST.get('status', '').strip()
    valid      = [c[0] for c in AgentStatus.STATUS_CHOICES]
    if new_status not in valid:
        return JsonResponse({'success': False, 'error': 'Invalid status.'}, status=400)

    agent_status, _ = AgentStatus.objects.get_or_create(agent=request.user)
    agent_status.status = new_status
    agent_status.save(update_fields=['status'])

    return JsonResponse({'success': True, 'status': new_status})


@staff_member_required
def get_quick_reply(request, reply_id):
    """Return the body of a quick-reply template and increment its usage counter."""
    reply = get_object_or_404(ChatQuickReply, id=reply_id, is_active=True)
    ChatQuickReply.objects.filter(pk=reply.pk).update(
        usage_count=models.F('usage_count') + 1
    )
    return JsonResponse({'success': True, 'message': reply.message, 'title': reply.title})


 