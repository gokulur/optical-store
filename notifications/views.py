# notifications/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from datetime import datetime

from .models import Notification, NotificationTemplate, StockAlert
from catalog.models import Product, ProductVariant


# ==================== NOTIFICATION HELPERS ====================
def send_notification(user, event_type, context_data=None, related_object_type=None, related_object_id=None):
    """
    Send notification based on template
    
    Args:
        user: User object
        event_type: Template event type
        context_data: Dict with template variables
        related_object_type: 'order', 'booking', etc.
        related_object_id: ID of related object
    """
    try:
        # Get template
        template = NotificationTemplate.objects.get(
            event_type=event_type,
            is_active=True
        )
        
        # Prepare context
        context = Context(context_data or {})
        
        # Render template
        subject = template.subject
        body = Template(template.body_template).render(context)
        
        # Determine recipient
        if template.channel == 'email':
            recipient = user.email
        elif template.channel == 'sms':
            recipient = user.phone
        else:
            recipient = user.email
        
        # Create notification record
        notification = Notification.objects.create(
            user=user,
            template=template,
            channel=template.channel,
            recipient=recipient,
            subject=subject,
            body=body,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            status='pending'
        )
        
        # Send notification
        if template.channel == 'email':
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                notification.status = 'sent'
                notification.sent_at = timezone.now()
            except Exception as e:
                notification.status = 'failed'
                notification.error_message = str(e)
        
        elif template.channel == 'sms':
            # TODO: Integrate SMS provider (Twilio, etc.)
            notification.status = 'sent'
            notification.sent_at = timezone.now()
        
        notification.save()
        return notification
        
    except NotificationTemplate.DoesNotExist:
        print(f"No template found for event: {event_type}")
        return None
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return None


# ==================== USER NOTIFICATIONS ====================
@login_required
def notification_list(request):
    """List user's notifications"""
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('template').order_by('-created_at')
    
    # Mark as read (you could add is_read field)
    # notifications.filter(is_read=False).update(is_read=True)
    
    context = {
        'notifications': notifications,
    }
    
    return render(request, 'notifications/notification_list.html', context)


@login_required
def notification_detail(request, notification_id):
    """View notification details"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    
    context = {
        'notification': notification,
    }
    
    return render(request, 'notifications/notification_detail.html', context)


# ==================== STOCK ALERTS ====================
@require_POST
def create_stock_alert(request):
    """Create stock alert for out-of-stock product"""
    try:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        
        # For contact lenses
        power_left = request.POST.get('power_left')
        power_right = request.POST.get('power_right')
        
        product = get_object_or_404(Product, id=product_id)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        
        # Check if alert already exists
        existing = StockAlert.objects.filter(
            product=product,
            variant=variant,
            customer_email=email,
            is_notified=False
        ).first()
        
        if existing:
            messages.info(request, 'You are already subscribed to alerts for this product.')
        else:
            StockAlert.objects.create(
                product=product,
                variant=variant,
                customer_email=email,
                customer_phone=phone,
                required_power_left=power_left if power_left else None,
                required_power_right=power_right if power_right else None
            )
            messages.success(request, 'You will be notified when this product is back in stock!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        
        messages.error(request, f'Error creating stock alert: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))


@login_required
def my_stock_alerts(request):
    """View user's stock alerts"""
    alerts = StockAlert.objects.filter(
        customer_email=request.user.email
    ).select_related('product', 'variant').order_by('-created_at')
    
    context = {
        'alerts': alerts,
    }
    
    return render(request, 'notifications/stock_alerts.html', context)


@login_required
@require_POST
def cancel_stock_alert(request, alert_id):
    """Cancel a stock alert"""
    alert = get_object_or_404(
        StockAlert,
        id=alert_id,
        customer_email=request.user.email
    )
    
    alert.delete()
    messages.success(request, 'Stock alert cancelled.')
    return redirect('notifications:my_stock_alerts')


# ==================== NOTIFICATION PREFERENCES ====================
@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    user = request.user
    
    if request.method == 'POST':
        user.email_notifications = request.POST.get('email_notifications') == 'on'
        user.sms_notifications = request.POST.get('sms_notifications') == 'on'
        user.save()
        
        messages.success(request, 'Notification preferences updated!')
        return redirect('notifications:preferences')
    
    context = {
        'user': user,
    }
    
    return render(request, 'notifications/preferences.html', context)


# ==================== ADMIN FUNCTIONS ====================
def notify_stock_alerts(product, variant=None):
    """
    Notify customers when product is back in stock
    Call this when inventory is updated
    """
    alerts = StockAlert.objects.filter(
        product=product,
        variant=variant,
        is_notified=False
    )
    
    for alert in alerts:
        try:
            # Send email
            subject = f"{product.name} is back in stock!"
            message = f"""
            Good news! The product you were waiting for is now available.
            
            {product.name}
            
            Shop now: {settings.SITE_URL}/product/{product.slug}/
            
            This is an automated notification. You will not receive further alerts for this product.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[alert.customer_email],
                fail_silently=True,
            )
            
            # Mark as notified
            alert.is_notified = True
            alert.notified_at = timezone.now()
            alert.save()
            
        except Exception as e:
            print(f"Error sending stock alert: {str(e)}")
            continue


# ==================== HELPER FUNCTIONS FOR OTHER APPS ====================
def send_order_confirmation(order):
    """Send order confirmation email"""
    context_data = {
        'customer_name': order.customer.first_name or 'Customer',
        'order_number': order.order_number,
        'total_amount': order.total_amount,
        'currency': order.currency,
        'order_url': f"{settings.SITE_URL}/orders/{order.order_number}/",
    }
    
    send_notification(
        user=order.customer,
        event_type='order_confirmed',
        context_data=context_data,
        related_object_type='order',
        related_object_id=order.id
    )


def send_order_shipped(order):
    """Send order shipped notification"""
    context_data = {
        'customer_name': order.customer.first_name or 'Customer',
        'order_number': order.order_number,
        'tracking_number': order.tracking_number,
        'carrier': order.carrier,
        'track_url': f"{settings.SITE_URL}/orders/{order.order_number}/track/",
    }
    
    send_notification(
        user=order.customer,
        event_type='order_shipped',
        context_data=context_data,
        related_object_type='order',
        related_object_id=order.id
    )


def send_eye_test_reminder(booking):
    """Send eye test appointment reminder"""
    context_data = {
        'customer_name': booking.customer.first_name if booking.customer else booking.customer_name,
        'appointment_date': booking.booking_date.strftime('%B %d, %Y'),
        'appointment_time': booking.booking_time.strftime('%I:%M %p'),
        'location_name': booking.location.name,
        'location_address': booking.location.address_line1,
    }
    
    if booking.customer:
        send_notification(
            user=booking.customer,
            event_type='eye_test_reminder',
            context_data=context_data,
            related_object_type='booking',
            related_object_id=booking.id
        )