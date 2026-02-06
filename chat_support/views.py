from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Max
from django.utils import timezone
from django.core.paginator import Paginator
from .models import ChatConversation, ChatMessage, ChatQuickReply, ChatOfflineMessage, AgentStatus


def get_client_ip(request):
    """Get client IP"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def assign_to_agent(conversation):
    """Auto-assign to available agent"""
    agents = AgentStatus.objects.filter(status='online').order_by('active_conversations')
    if agents.exists():
        agent = agents.first()
        if agent.is_available():
            conversation.assigned_to = agent.agent
            conversation.status = 'in_progress'
            conversation.save()
            agent.active_conversations += 1
            agent.save()
            ChatMessage.objects.create(
                conversation=conversation,
                sender_name='System',
                message=f'Assigned to {agent.agent.username}',
                is_from_customer=False,
                message_type='system'
            )


# CUSTOMER VIEWS

def chat_widget(request):
    """Chat widget"""
    is_online = AgentStatus.objects.filter(status='online').exists()
    return render(request, 'chat_support/widget.html', {'is_online': is_online})


def start_chat(request):
    """Start chat"""
    if request.method == 'POST':
        subject = request.POST.get('subject', 'General Inquiry')
        message_text = request.POST.get('message', '')
        
        if request.user.is_authenticated:
            conv = ChatConversation.objects.create(
                user=request.user,
                subject=subject,
                ip_address=get_client_ip(request)
            )
        else:
            conv = ChatConversation.objects.create(
                guest_name=request.POST.get('guest_name', 'Guest'),
                guest_email=request.POST.get('guest_email', ''),
                subject=subject,
                ip_address=get_client_ip(request)
            )
        
        if message_text:
            ChatMessage.objects.create(
                conversation=conv,
                sender=request.user if request.user.is_authenticated else None,
                sender_name=conv.get_display_name(),
                message=message_text,
                is_from_customer=True
            )
        
        assign_to_agent(conv)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'conversation_id': conv.conversation_id,
                'redirect_url': f'/chat/conversation/{conv.conversation_id}/'
            })
        
        return redirect('chat:conversation', conversation_id=conv.conversation_id)
    
    return render(request, 'chat_support/start_chat.html')


def chat_conversation(request, conversation_id):
    """Customer conversation view"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    
    # Mark staff messages as read
    conversation.messages.filter(is_from_customer=False, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    
    messages = conversation.messages.all()
    
    return render(request, 'chat_support/conversation.html', {
        'conversation': conversation,
        'messages': messages
    })


@require_http_methods(["POST"])
def send_message(request, conversation_id):
    """Send message"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    
    message_text = request.POST.get('message', '').strip()
    attachment = request.FILES.get('attachment')
    
    if not message_text and not attachment:
        return JsonResponse({'success': False, 'error': 'Empty message'})
    
    is_staff = request.user.is_authenticated and request.user.is_staff
    
    msg = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user if request.user.is_authenticated else None,
        sender_name=request.user.get_full_name() if is_staff else conversation.get_display_name(),
        message=message_text,
        attachment=attachment,
        is_from_customer=not is_staff,
        message_type='image' if attachment and attachment.content_type.startswith('image/') else 'file' if attachment else 'text'
    )
    
    return JsonResponse({
        'success': True,
        'message': {
            'id': msg.id,
            'message': msg.message,
            'sender_name': msg.sender_name,
            'is_from_customer': msg.is_from_customer,
            'created_at': msg.created_at.strftime('%H:%M'),
            'attachment_url': msg.attachment.url if msg.attachment else None
        }
    })


def get_messages(request, conversation_id):
    """Get new messages (polling)"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    last_id = int(request.GET.get('last_message_id', 0))
    
    messages = conversation.messages.filter(id__gt=last_id)
    
    is_staff = request.user.is_authenticated and request.user.is_staff
    if not is_staff:
        messages.filter(is_from_customer=False, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
    
    msg_list = []
    for m in messages:
        msg_list.append({
            'id': m.id,
            'message': m.message,
            'sender_name': m.sender_name or 'Guest',
            'is_from_customer': m.is_from_customer,
            'created_at': m.created_at.strftime('%H:%M'),
            'attachment_url': m.attachment.url if m.attachment else None,
            'message_type': m.message_type
        })
    
    return JsonResponse({'success': True, 'messages': msg_list})


@require_http_methods(["POST"])
def rate_conversation(request, conversation_id):
    """Rate conversation"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    conversation.rating = request.POST.get('rating')
    conversation.feedback = request.POST.get('feedback', '')
    conversation.save()
    return JsonResponse({'success': True})


def offline_message(request):
    """Offline message"""
    if request.method == 'POST':
        ChatOfflineMessage.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            subject=request.POST.get('subject'),
            message=request.POST.get('message'),
            ip_address=get_client_ip(request)
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Message received. We will contact you soon.'
            })
        
        return redirect('chat:start_chat')
    
    return render(request, 'chat_support/offline_form.html')


# AGENT VIEWS

@staff_member_required
def agent_dashboard(request):
    """Agent dashboard"""
    conversations = ChatConversation.objects.select_related('user', 'assigned_to').annotate(
        message_count=Count('messages'),
        last_message_time=Max('messages__created_at')
    )
    
    # Filters
    status = request.GET.get('status')
    if status:
        conversations = conversations.filter(status=status)
    
    assigned = request.GET.get('assigned_to')
    if assigned == 'me':
        conversations = conversations.filter(assigned_to=request.user)
    elif assigned == 'unassigned':
        conversations = conversations.filter(assigned_to__isnull=True)
    
    priority = request.GET.get('priority')
    if priority:
        conversations = conversations.filter(priority=priority)
    
    conversations = conversations.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(conversations, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    
    # Stats
    stats = {
        'total': ChatConversation.objects.count(),
        'open': ChatConversation.objects.filter(status='open').count(),
        'in_progress': ChatConversation.objects.filter(status='in_progress').count(),
        'my_active': ChatConversation.objects.filter(
            assigned_to=request.user, status__in=['open', 'in_progress']
        ).count(),
        'unassigned': ChatConversation.objects.filter(assigned_to__isnull=True).count()
    }
    
    return render(request, 'chat_support/agent_dashboard.html', {
        'conversations': page,
        'stats': stats
    })


@staff_member_required
def agent_conversation(request, conversation_id):
    """Agent conversation view"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    
    conversation.messages.filter(is_from_customer=True, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    
    messages = conversation.messages.all()
    quick_replies = ChatQuickReply.objects.filter(is_active=True)[:10]
    
    return render(request, 'chat_support/agent_conversation.html', {
        'conversation': conversation,
        'messages': messages,
        'quick_replies': quick_replies
    })


@staff_member_required
@require_http_methods(["POST"])
def assign_conversation(request, conversation_id):
    """Assign conversation"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    conversation.assigned_to = request.user
    conversation.status = 'in_progress'
    conversation.save()
    
    ChatMessage.objects.create(
        conversation=conversation,
        sender_name='System',
        message=f'Assigned to {request.user.username}',
        is_from_customer=False,
        message_type='system'
    )
    
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(["POST"])
def update_status(request, conversation_id):
    """Update status"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    conversation.status = request.POST.get('status')
    
    if conversation.status in ['resolved', 'closed']:
        conversation.closed_at = timezone.now()
    
    conversation.save()
    
    ChatMessage.objects.create(
        conversation=conversation,
        sender_name='System',
        message=f'Status: {conversation.get_status_display()}',
        is_from_customer=False,
        message_type='system'
    )
    
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(["POST"])
def update_priority(request, conversation_id):
    """Update priority"""
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)
    conversation.priority = request.POST.get('priority')
    conversation.save()
    return JsonResponse({'success': True})


@staff_member_required
@require_http_methods(["POST"])
def agent_status_update(request):
    """Update agent status"""
    agent_status, created = AgentStatus.objects.get_or_create(agent=request.user)
    agent_status.status = request.POST.get('status')
    agent_status.save()
    return JsonResponse({'success': True})


@staff_member_required
def get_quick_reply(request, reply_id):
    """Get quick reply"""
    reply = get_object_or_404(ChatQuickReply, id=reply_id)
    reply.usage_count += 1
    reply.save()
    return JsonResponse({'success': True, 'message': reply.message})