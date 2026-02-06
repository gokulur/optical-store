from django.db import models
from django.conf import settings
from django.utils import timezone
import random
import string


# ============================================
# CHAT CONVERSATION
# ============================================

class ChatConversation(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )

    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )

    conversation_id = models.CharField(max_length=20, unique=True, editable=False)

    # ✅ FIXED HERE
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversations'
    )

    guest_name = models.CharField(max_length=100, blank=True)
    guest_email = models.EmailField(blank=True)

    subject = models.CharField(max_length=200, default="General Inquiry")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    # ✅ FIXED HERE
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_chats'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    rating = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.conversation_id} - {self.get_display_name()}"

    def save(self, *args, **kwargs):
        if not self.conversation_id:
            timestamp = timezone.now().strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.conversation_id = f"CHAT{timestamp}{random_str}"
        super().save(*args, **kwargs)

    def get_display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or self.guest_email or 'Guest'

    def unread_count_for_staff(self):
        return self.messages.filter(is_from_customer=True, is_read=False).count()

    def unread_count_for_customer(self):
        return self.messages.filter(is_from_customer=False, is_read=False).count()


# ============================================
# CHAT MESSAGE
# ============================================

class ChatMessage(models.Model):
    TYPE_CHOICES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    )

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    # ✅ FIXED HERE
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    sender_name = models.CharField(max_length=100, blank=True)

    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='text')
    message = models.TextField()

    attachment = models.FileField(upload_to='chat_files/%Y/%m/', null=True, blank=True)

    is_from_customer = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.conversation.conversation_id}"


# ============================================
# QUICK REPLIES
# ============================================

class ChatQuickReply(models.Model):
    title = models.CharField(max_length=100)
    message = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-usage_count']

    def __str__(self):
        return self.title


# ============================================
# OFFLINE MESSAGE
# ============================================

class ChatOfflineMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"


# ============================================
# AGENT STATUS
# ============================================

class AgentStatus(models.Model):
    STATUS_CHOICES = (
        ('online', 'Online'),
        ('away', 'Away'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
    )

    # ✅ FIXED HERE
    agent = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_status'
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='offline')
    last_activity = models.DateTimeField(auto_now=True)
    active_conversations = models.IntegerField(default=0)
    max_conversations = models.IntegerField(default=5)

    def __str__(self):
        return f"{self.agent.username} - {self.status}"

    def is_available(self):
        return self.status == 'online' and self.active_conversations < self.max_conversations
