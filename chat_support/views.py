from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Max, F, Q
from django.utils import timezone
from django.core.paginator import Paginator
from .models import ChatConversation, ChatMessage, ChatQuickReply, ChatOfflineMessage, AgentStatus


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _json_error(message, status=400):
    """Consistent JSON error response helper."""
    return JsonResponse({'success': False, 'error': message}, status=status)


def assign_to_agent(conversation):
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
    if request.method != 'POST':
        return redirect('/')

    subject = request.POST.get('subject', 'Website Inquiry').strip() or 'Website Inquiry'
    text    = request.POST.get('message', '').strip()
    attach  = request.FILES.get('attachment')

    if request.user.is_authenticated:
        conv = ChatConversation.objects.create(
            user=request.user,
            subject=subject,
            ip_address=get_client_ip(request),
        )
    else:
        conv = ChatConversation.objects.create(
            guest_name=request.POST.get('guest_name', 'Guest').strip() or 'Guest',
            guest_email=request.POST.get('guest_email', '').strip(),
            subject=subject,
            ip_address=get_client_ip(request),
        )

    if text or attach:
        msg_type = (
            'image' if attach and attach.content_type.startswith('image/') else
            'file'  if attach else
            'text'
        )
        ChatMessage.objects.create(
            conversation=conv,
            sender=request.user if request.user.is_authenticated else None,
            sender_name=conv.get_display_name(),
            message=text,
            attachment=attach,
            is_from_customer=True,
            message_type=msg_type,
        )

    assign_to_agent(conv)
    return JsonResponse({'success': True, 'conversation_id': conv.conversation_id})


# ─────────────────────────────────────────────
# ✅ FIX: send_message now properly handles both
#    customer (unauthenticated) and staff (authenticated)
#    WITHOUT throwing errors either way.
# ─────────────────────────────────────────────
@require_POST
def send_message(request, conversation_id):
    """
    Shared send endpoint used by:
      - Customer widget  (unauthenticated or logged-in customer)
      - Admin panel      (staff user, request.user.is_staff == True)

    ✅ FIX 1: Added @require_POST — prevents accidental GET which returned
              status 405 JSON but could confuse the JS chain.

    ✅ FIX 2: Wrapped the entire body in try/except so any unexpected DB
              error returns clean JSON instead of an HTML 500 page.
              HTML 500 was the primary cause of "Network error" in the UI —
              r.json() threw a SyntaxError on the HTML body.

    ✅ FIX 3: conv.save(update_fields=['status']) now only runs when the
              status field actually changed, preventing a spurious DB write
              and eliminating any risk of a FieldError on restricted models.

    ✅ FIX 4: Staff auth check uses request.user.is_staff (same as the
              adminpanel decorator) so there is no ambiguity.
    """
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    text   = request.POST.get('message', '').strip()
    attach = request.FILES.get('attachment')

    if not text and not attach:
        return _json_error('Empty message.')

    try:
        is_staff = request.user.is_authenticated and request.user.is_staff

        msg_type = (
            'image' if attach and attach.content_type.startswith('image/') else
            'file'  if attach else
            'text'
        )
        sender_name = (
            (request.user.get_full_name() or request.user.username)
            if is_staff
            else conv.get_display_name()
        )

        msg = ChatMessage.objects.create(
            conversation=conv,
            sender=request.user if request.user.is_authenticated else None,
            sender_name=sender_name,
            message=text,
            attachment=attach,
            is_from_customer=not is_staff,
            message_type=msg_type,
        )

        # ✅ FIX 3: only save status when it actually needs to change.
        # Previously conv.save(update_fields=['status']) ran unconditionally,
        # which on some DB setups or if status was a property would raise an
        # exception → Django returned HTML 500 → JS r.json() failed → "Network error".
        if not is_staff and conv.status in ('resolved', 'closed'):
            conv.status = 'open'
            conv.save(update_fields=['status'])
        # For staff messages: don't touch the status at all unless you want to.
        # (Staff sending a message should not auto-reopen a resolved conversation.)

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
        # ✅ FIX 2: catch-all so Django never returns an HTML error page to
        #           the JS fetch() call.  The JS .catch() block fires when
        #           r.json() throws — which happens on any non-JSON body
        #           (HTML 500, HTML 403, redirect HTML, etc.).
        import logging
        logging.getLogger('chat_support').exception('send_message error: %s', e)
        return JsonResponse(
            {'success': False, 'error': 'Server error. Please try again.'},
            status=500
        )


def get_messages(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    try:
        last_id = int(request.GET.get('last_message_id', 0))
    except ValueError:
        last_id = 0

    is_staff = request.user.is_authenticated and request.user.is_staff
    qs = conv.messages.filter(id__gt=last_id)

    if not is_staff:
        qs.filter(is_from_customer=False, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
    else:
        qs.filter(is_from_customer=True, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

    return JsonResponse({
        'success': True,
        'messages': [{
            'id':               m.id,
            'message':          m.message,
            'sender_name':      m.sender_name or 'Support',
            'is_from_customer': m.is_from_customer,
            'message_type':     m.message_type,
            'created_at':       m.created_at.strftime('%H:%M'),
            'attachment_url':   m.attachment.url if m.attachment else None,
        } for m in qs]
    })


@require_http_methods(['POST'])
def rate_conversation(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    try:
        rating = int(request.POST.get('rating', 0))
        assert 1 <= rating <= 5
    except (TypeError, ValueError, AssertionError):
        return _json_error('Rating must be 1–5.')
    conv.rating = rating
    conv.save(update_fields=['rating'])
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────
# AGENT VIEWS
# ─────────────────────────────────────────────

@staff_member_required
def agent_dashboard(request):
    qs = (ChatConversation.objects
          .select_related('user', 'assigned_to')
          .annotate(
              message_count=Count('messages'),
              last_message_time=Max('messages__created_at')
          ))

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
            Q(guest_name__icontains=q)
        )

    qs = qs.order_by('-created_at')
    page = Paginator(qs, 20).get_page(request.GET.get('page', 1))
    base = ChatConversation.objects
    my_status, _ = AgentStatus.objects.get_or_create(agent=request.user)

    return render(request, 'chat/agent_dashboard.html', {
        'conversations': page,
        'my_status': my_status,
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
    conv.messages.filter(
        is_from_customer=True, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return render(request, 'chat/agent_conversation.html', {
        'conversation':  conv,
        'messages':      conv.messages.all(),
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
    if new not in [c[0] for c in ChatConversation.STATUS_CHOICES]:
        return _json_error('Invalid status.')

    conv.status = new
    fields_to_save = ['status']

    if new in ('resolved', 'closed'):
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
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(['POST'])
def update_priority(request, conversation_id):
    conv = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    new = request.POST.get('priority', '').strip()
    if new not in [c[0] for c in ChatConversation.PRIORITY_CHOICES]:
        return _json_error('Invalid priority.')
    conv.priority = new
    conv.save(update_fields=['priority'])
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(['POST'])
def agent_status_update(request):
    new = request.POST.get('status', '').strip()
    if new not in [c[0] for c in AgentStatus.STATUS_CHOICES]:
        return _json_error('Invalid status.')
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