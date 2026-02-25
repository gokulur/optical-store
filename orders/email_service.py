# orders/email_service.py
"""
Order confirmation email service.
Follows the same pattern used in users/views.py (EmailMessage with render_to_string).
"""

import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.timezone import localtime

logger = logging.getLogger(__name__)


# ── Payment method display names ──────────────────────────────
PAYMENT_METHOD_LABELS = {
    'cash_on_delivery': '💵 Cash on Delivery',
    'sadad':            '💚 Sadad',
    'stripe':           '💳 Credit / Debit Card',
    'razorpay':         '🏦 Razorpay',
    'paypal':           '🌐 PayPal',
}


def send_order_confirmation_email(order):
    """
    Send a beautiful HTML order confirmation email to the customer.

    Usage — call this right after the order is confirmed, e.g. in place_order():

        from .email_service import send_order_confirmation_email
        send_order_confirmation_email(order)

    Returns True on success, False on failure (never raises).
    """
    try:
        customer_email = order.customer_email or order.customer.email

        # ── Build item list for the template ──────────────────
        items_data = []
        for item in order.items.select_related('product', 'lens_option') \
                               .prefetch_related('product__images'):
            # Try to get an absolute image URL
            image_url = None
            try:
                if item.product.images.first():
                    image_url = item.product.images.first().image.url
                elif hasattr(item.product, 'image') and item.product.image:
                    image_url = item.product.image.url
                # Make absolute if it's a relative path
                if image_url and image_url.startswith('/'):
                    site_url = getattr(settings, 'SITE_URL',
                                       f"https://{getattr(settings, 'ALLOWED_HOSTS', [''])[0]}")
                    image_url = site_url.rstrip('/') + image_url
            except Exception:
                image_url = None

            items_data.append({
                'product_name':    item.product_name,
                'quantity':        item.quantity,
                'unit_price':      str(item.unit_price),
                'subtotal':        str(item.subtotal),
                'currency':        order.currency,
                'lens_option_name': item.lens_option_name or '',
                'image_url':       image_url or '',
            })

        # ── Estimated delivery copy ────────────────────────────
        if order.payment_method == 'cash_on_delivery':
            estimated_delivery = '3–5 business days'
        else:
            estimated_delivery = '2–4 business days'

        # ── Site URL ──────────────────────────────────────────
        site_url = getattr(settings, 'SITE_URL', '')
        if not site_url:
            hosts = getattr(settings, 'ALLOWED_HOSTS', [''])
            site_url = f"https://{hosts[0]}" if hosts and hosts[0] not in ('*', '') else 'https://alameen-optics.com'

        order_detail_url = f"{site_url.rstrip('/')}/orders/{order.order_number}/"

        # ── Template context ──────────────────────────────────
        context = {
            'customer_name':          order.customer_name or order.customer.get_full_name() or 'Valued Customer',
            'order_number':           order.order_number,
            'order_date':             localtime(order.created_at).strftime('%B %d, %Y at %I:%M %p'),
            'payment_method_display': PAYMENT_METHOD_LABELS.get(order.payment_method, order.payment_method),
            'payment_status':         order.payment_status,
            'estimated_delivery':     estimated_delivery,
            'order_items':            items_data,
            'currency':               order.currency,
            'subtotal':               str(order.subtotal),
            'discount_amount':        str(order.discount_amount),
            'shipping_amount':        str(order.shipping_amount),
            'tax_amount':             str(order.tax_amount),
            'total_amount':           str(order.total_amount),
            'shipping_name':          order.customer_name,
            'shipping_line1':         order.shipping_address_line1,
            'shipping_line2':         order.shipping_address_line2 or '',
            'shipping_city':          order.shipping_city,
            'shipping_state':         order.shipping_state or '',
            'shipping_postal':        order.shipping_postal_code or '',
            'shipping_country':       order.shipping_country,
            'shipping_phone':         order.customer_phone or '',
            'order_detail_url':       order_detail_url,
            'site_url':               site_url,
            'support_email':          getattr(settings, 'SUPPORT_EMAIL',
                                              getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@alameen-optics.com')),
        }

        # ── Render HTML ───────────────────────────────────────
        html_body = render_to_string('order_confirmation_email.html', context)

        # ── Send ──────────────────────────────────────────────
        subject = f"✅ Order Confirmed — #{order.order_number} | Al Ameen Optics"

        email = EmailMessage(
            subject=subject,
            body=html_body,
            to=[customer_email],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@alameen-optics.com'),
        )
        email.content_subtype = 'html'   # Critical: tells Django this is HTML, not plain text
        email.send(fail_silently=False)

        logger.info(f"Order confirmation email sent to {customer_email} for order {order.order_number}")
        return True

    except Exception as e:
        # Never crash the order flow because of email failure
        logger.error(f"Failed to send order confirmation email for {order.order_number}: {e}", exc_info=True)
        return False