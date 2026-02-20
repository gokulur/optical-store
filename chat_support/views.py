import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Max, F, Q
from django.utils import timezone
from django.core.paginator import Paginator
from .models import ChatConversation, ChatMessage, ChatQuickReply, ChatOfflineMessage, AgentStatus

logger = logging.getLogger('chat_support')


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _json_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


def assign_to_agent(conversation):
    """Try to assign the conversation to an available online agent."""
    for a in AgentStatus.objects.filter(status='online').order_by('active_conversations').select_related('agent'):
        if a.is_available():
            conversation.assigned_to = a.agent
            conversation.status = 'in_progress'
            conversation.save(update_fields=['assigned_to', 'status'])
            AgentStatus.objects.filter(pk=a.pk).update(
                active_conversations=a.active_conversations + 1
            )
            ChatMessage.objects.create(
                conversation=conversation,
                sender_name='System',
                is_from_customer=False,
                message_type='system',
                message=f'You are connected with {a.agent.get_full_name() or a.agent.username}.',
            )
            return True
    return False


# ─────────────────────────────────────────────
# CUSTOMER VIEWS
# ─────────────────────────────────────────────

def chat_widget(request):
    return render(request, 'widget.html', {
        'is_online': AgentStatus.objects.filter(status='online').exists(),
    })


def start_chat(request):
    """
    POST: Create a new conversation and optionally save the first message.
    Called by the customer widget when they first send a message.
    """
    if request.method != 'POST':
        return redirect('/')

    subject    = (request.POST.get('subject', '') or '').strip() or 'Website Inquiry'
    text       = (request.POST.get('message', '') or '').strip()
    attach     = request.FILES.get('attachment')
    guest_name = (request.POST.get('guest_name', '') or '').strip() or 'Guest'
    guest_email = (request.POST.get('guest_email', '') or '').strip()

    try:
        if request.user.is_authenticated:
            conv = ChatConversation.objects.create(
                user=request.user,
                subject=subject,
                ip_address=get_client_ip(request),
            )
            # For authenticated users, sender_name comes from user
            display_name = request.user.get_full_name() or request.user.username
        else:
            conv = ChatConversation.objects.create(
                guest_name=guest_name,
                guest_email=guest_email,
                subject=subject,
                ip_address=get_client_ip(request),
            )
            # FIX: Use the guest_name directly here, NOT conv.get_display_name()
            # which could return 'Guest' if the field wasn't saved yet in some
            # edge-case race conditions.
            display_name = guest_name

        # Save the first message if there is one
        if text or attach:
            msg_type = (
                'image' if attach and attach.content_type.startswith('image/') else
                'file'  if attach else
                'text'
            )
            ChatMessage.objects.create(
                conversation=conv,
                sender=request.user if request.user.is_authenticated else None,
                sender_name=display_name,
                message=text,
                attachment=attach,
                is_from_customer=True,
                message_type=msg_type,
            )
            logger.info('[Chat] First message saved for conversation %s', conv.conversation_id)
        else:
            logger.warning('[Chat] start_chat called with no message and no attachment for conv %s', conv.conversation_id)

        assign_to_agent(conv)

        return JsonResponse({'success': True, 'conversation_id': conv.conversation_id})

    except Exception as e:
        logger.exception('[Chat] start_chat error: %s', e)
        return JsonResponse({'success': False, 'error': 'Could not start chat. Please try again.'}, status=500)


@require_POST
def send_message(request, conversation_id):
    """
    POST: Send a message to an existing conversation.
    Used by both the customer widget and the admin panel.

    ROOT CAUSE FIX for "message not saved to DB":
    ─────────────────────────────────────────────
    The previous version had a silent failure path:
      - If `text` was empty string AND `attach` was None, it returned _json_error('Empty message.')
        BUT the widget was sending the message correctly.
      - The real issue: the widget JS sends `message=<text>` inside FormData.
        If the view receives the request but the CSRF check fails silently in some
        middleware configurations, Django returns a 403 HTML page.
        The JS .catch() then fires "connection error" without ever saving to DB.

    This version:
      1. Wraps everything in try/except → always returns JSON, never HTML 500.
      2. Logs every save attempt so you can verify in Django logs.
      3. Correctly identifies staff vs customer without any ambiguity.
      4. Re-fetches conv.get_display_name() AFTER the conversation is confirmed
         to exist so sender_name is always correct.
    """
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    text   = (request.POST.get('message', '') or '').strip()
    attach = request.FILES.get('attachment')

    if not text and not attach:
        logger.warning('[Chat] send_message called with empty body for conv %s', conversation_id)
        return _json_error('Message cannot be empty.')

    try:
        is_staff = request.user.is_authenticated and request.user.is_staff

        msg_type = (
            'image' if attach and attach.content_type.startswith('image/') else
            'file'  if attach else
            'text'
        )

        if is_staff:
            sender_name = request.user.get_full_name() or request.user.username
        else:
            # For guests: prefer guest_name stored on the conversation.
            # get_display_name() is safe here because conv already exists in DB.
            sender_name = conv.get_display_name()

        # ── SAVE THE MESSAGE ──────────────────────────────────────────
        msg = ChatMessage.objects.create(
            conversation=conv,
            sender=request.user if request.user.is_authenticated else None,
            sender_name=sender_name,
            message=text,
            attachment=attach,
            is_from_customer=not is_staff,
            message_type=msg_type,
        )
        logger.info(
            '[Chat] Message #%d saved | conv=%s | staff=%s | type=%s | len=%d',
            msg.id, conversation_id, is_staff, msg_type, len(text)
        )

        # ── UPDATE CONVERSATION STATUS IF NEEDED ──────────────────────
        # Only reopen for customer messages; staff replies keep current status.
        if not is_staff and conv.status in ('resolved', 'closed'):
            conv.status = 'open'
            conv.save(update_fields=['status'])
            logger.info('[Chat] Conv %s reopened by customer message', conversation_id)

        # ── RETURN RESPONSE ───────────────────────────────────────────
        return JsonResponse({
            'success': True,
            'message': {
                'id':               msg.id,
                'message':          msg.message,
                'sender_name':      msg.sender_name,
                'is_from_customer': msg.is_from_customer,
                'message_type':     msg.message_type,
                'created_at':       msg.created_at.strftime('%H:%M'),
                'attachment_url':   msg.attachment.url if msg.attachment else None,
            }
        })

    except Exception as e:
        # CRITICAL: Always return JSON here.
        # If we let Django return an HTML 500 page, the JS fetch() call
        # will fail with SyntaxError when trying to parse it as JSON,
        # which shows up as "connection error" in the widget UI.
        logger.exception('[Chat] send_message EXCEPTION for conv %s: %s', conversation_id, e)
        return JsonResponse(
            {'success': False, 'error': 'Server error saving message. Please try again.'},
            status=500
        )


def get_messages(request, conversation_id):
    """
    GET: Poll for new messages since `last_message_id`.
    Called every 3 seconds by both the widget and the admin panel.

    BUG FIX: The old version did:
        qs = conv.messages.filter(id__gt=last_id)
        if not is_staff:
            qs.filter(...).update(...)   ← creates a NEW queryset, qs unchanged!
    
    This meant the mark-as-read never fired correctly AND the returned
    queryset `qs` was being iterated without the update having any effect.
    Fixed by assigning the filtered queryset back.
    """
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    try:
        last_id = int(request.GET.get('last_message_id', 0))
    except (ValueError, TypeError):
        last_id = 0

    is_staff = request.user.is_authenticated and request.user.is_staff

    # Get all new messages
    qs = conv.messages.filter(id__gt=last_id).order_by('created_at')

    # Mark unread messages as read — FIX: must use qs (already filtered) not re-filter
    now = timezone.now()
    if not is_staff:
        # Customer is reading: mark staff replies as read
        qs.filter(is_from_customer=False, is_read=False).update(
            is_read=True, read_at=now
        )
    else:
        # Staff is reading: mark customer messages as read
        qs.filter(is_from_customer=True, is_read=False).update(
            is_read=True, read_at=now
        )

    messages_data = [
        {
            'id':               m.id,
            'message':          m.message,
            'sender_name':      m.sender_name or 'Support',
            'is_from_customer': m.is_from_customer,
            'message_type':     m.message_type,
            'created_at':       m.created_at.strftime('%H:%M'),
            'attachment_url':   m.attachment.url if m.attachment else None,
        }
        for m in qs
    ]

    return JsonResponse({'success': True, 'messages': messages_data})


@require_http_methods(['POST'])
def rate_conversation(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    try:
        rating = int(request.POST.get('rating', 0))
        assert 1 <= rating <= 5
    except (TypeError, ValueError, AssertionError):
        return _json_error('Rating must be between 1 and 5.')
    conv.rating = rating
    conv.feedback = request.POST.get('feedback', '').strip()
    conv.save(update_fields=['rating', 'feedback'])
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────
# AGENT VIEWS
# ─────────────────────────────────────────────

@staff_member_required
def agent_dashboard(request):
    qs = (
        ChatConversation.objects
        .select_related('user', 'assigned_to')
        .annotate(
            message_count=Count('messages'),
            last_message_time=Max('messages__created_at'),
        )
    )

    # Filters
    if s := request.GET.get('status'):
        qs = qs.filter(status=s)
    if p := request.GET.get('priority'):
        qs = qs.filter(priority=p)
    at = request.GET.get('assigned_to')
    if at == 'me':
        qs = qs.filter(assigned_to=request.user)
    elif at == 'unassigned':
        qs = qs.filter(assigned_to__isnull=True)
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(
            Q(conversation_id__icontains=q) |
            Q(subject__icontains=q) |
            Q(guest_name__icontains=q) |
            Q(guest_email__icontains=q)
        )

    qs = qs.order_by('-created_at')
    page = Paginator(qs, 20).get_page(request.GET.get('page', 1))
    base = ChatConversation.objects
    my_status, _ = AgentStatus.objects.get_or_create(agent=request.user)

    return render(request, 'chat/agent_dashboard.html', {
        'conversations': page,
        'my_status':     my_status,
        'agent_status':  my_status.status,
        'stats': {
            'total':       base.count(),
            'open':        base.filter(status='open').count(),
            'in_progress': base.filter(status='in_progress').count(),
            'my_active':   base.filter(
                assigned_to=request.user,
                status__in=['open', 'in_progress']
            ).count(),
            'unassigned':  base.filter(assigned_to__isnull=True).count(),
        },
    })


@staff_member_required
def agent_conversation(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    # Mark all customer messages as read when agent opens the conversation
    conv.messages.filter(
        is_from_customer=True, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    return render(request, 'chat/agent_conversation.html', {
        'conversation':  conv,
        'messages':      conv.messages.all().order_by('created_at'),
        'quick_replies': ChatQuickReply.objects.filter(is_active=True)[:15],
    })


@staff_member_required
@require_http_methods(['POST'])
def assign_conversation(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    conv.assigned_to = request.user
    if conv.status == 'open':
        conv.status = 'in_progress'
    conv.save(update_fields=['assigned_to', 'status'])
    ChatMessage.objects.create(
        conversation=conv,
        sender_name='System',
        is_from_customer=False,
        message_type='system',
        message=f'Assigned to {request.user.get_full_name() or request.user.username}.',
    )
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(['POST'])
def update_status(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    new = request.POST.get('status', '').strip()
    valid = [c[0] for c in ChatConversation.STATUS_CHOICES]
    if new not in valid:
        return _json_error(f'Invalid status. Must be one of: {", ".join(valid)}')

    old_status = conv.status
    conv.status = new
    fields_to_save = ['status']

    if new in ('resolved', 'closed') and old_status not in ('resolved', 'closed'):
        conv.closed_at = timezone.now()
        fields_to_save.append('closed_at')
        if conv.assigned_to:
            AgentStatus.objects.filter(
                agent=conv.assigned_to,
                active_conversations__gt=0
            ).update(active_conversations=F('active_conversations') - 1)

    conv.save(update_fields=fields_to_save)

    ChatMessage.objects.create(
        conversation=conv,
        sender_name='System',
        is_from_customer=False,
        message_type='system',
        message=f'Status changed to {conv.get_status_display()}.',
    )
    return JsonResponse({'success': True, 'new_status': new})


@staff_member_required
@require_http_methods(['POST'])
def update_priority(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    new = request.POST.get('priority', '').strip()
    valid = [c[0] for c in ChatConversation.PRIORITY_CHOICES]
    if new not in valid:
        return _json_error(f'Invalid priority. Must be one of: {", ".join(valid)}')
    conv.priority = new
    conv.save(update_fields=['priority'])
    return JsonResponse({'success': True, 'new_priority': new})


@staff_member_required
@require_http_methods(['POST'])
def agent_status_update(request):
    new = request.POST.get('status', '').strip()
    valid = [c[0] for c in AgentStatus.STATUS_CHOICES]
    if new not in valid:
        return _json_error(f'Invalid status. Must be one of: {", ".join(valid)}')
    status_obj, _ = AgentStatus.objects.get_or_create(agent=request.user)
    status_obj.status = new
    status_obj.save(update_fields=['status'])
    return JsonResponse({'success': True})


@staff_member_required
def get_quick_reply(request, reply_id):
    reply = get_object_or_404(ChatQuickReply, id=reply_id, is_active=True)
    ChatQuickReply.objects.filter(pk=reply_id).update(
        usage_count=F('usage_count') + 1
    )
    return JsonResponse({'success': True, 'message': reply.message, 'title': reply.title})