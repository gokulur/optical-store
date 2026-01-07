 # notifications/models.py
from django.db import models
from django.conf import settings


class NotificationTemplate(models.Model):
    """Email/SMS templates"""
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    EVENT_TYPES = [
        ('order_confirmed', 'Order Confirmed'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('eye_test_reminder', 'Eye Test Reminder'),
        ('prescription_expiring', 'Prescription Expiring'),
        ('welcome', 'Welcome Email'),
        ('password_reset', 'Password Reset'),
        ('stock_alert', 'Stock Alert'),
    ]
    
    name = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100, choices=EVENT_TYPES, unique=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    subject = models.CharField(max_length=200, blank=True)  # For email
    body_template = models.TextField()  # Can contain variables like {{customer_name}}
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_templates'


class Notification(models.Model):
    """Sent notifications log"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    channel = models.CharField(max_length=20)
    recipient = models.CharField(max_length=255)  # Email or phone
    
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    
    status = models.CharField(max_length=50, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ], default='pending')
    
    error_message = models.TextField(blank=True)
    
    # Reference to related object
    related_object_type = models.CharField(max_length=50, blank=True)  # 'order', 'booking', etc.
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]


class StockAlert(models.Model):
    """Customer stock alerts for out-of-stock products"""
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='stock_alerts')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, null=True, blank=True)
    
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # For contact lenses with specific power
    required_power_left = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    required_power_right = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    is_notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'is_notified']),
            models.Index(fields=['customer_email']),
        ]