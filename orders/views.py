# orders/views.py - COMPLETE WITH ALL PAYMENT INTEGRATIONS
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from decimal import Decimal
import random
import string
import json
import logging

from django.conf import settings
from .models import Order, OrderItem, OrderItemLensAddOn, OrderStatusHistory, PaymentTransaction
from cart.models import Cart, CartItem
from users.models import Address
from cart.views import get_or_create_cart
from .payment_services import (
    StripePaymentService,
    RazorpayPaymentService,
    PayPalPaymentService,
    SadadPaymentService,
    SadadPaymentError,
    PaymentGatewayFactory,
    PaymentGatewayError,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def generate_order_number():
    timestamp  = timezone.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"


def generate_transaction_id():
    timestamp  = timezone.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"TXN-{timestamp}-{random_str}"


# ─────────────────────────────────────────────────────────────
# CHECKOUT
# ─────────────────────────────────────────────────────────────

@login_required
def checkout(request):
    cart       = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option'
    ).prefetch_related('lens_addons')

    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart:cart_view')

    shipping_addresses = request.user.addresses.all()
    default_shipping   = shipping_addresses.filter(is_default_shipping=True).first()
    default_billing    = shipping_addresses.filter(is_default_billing=True).first()

    subtotal = Decimal('0.00')
    for item in cart_items:
        item_total = item.unit_price * item.quantity
        if item.lens_price:
            item_total += item.lens_price * item.quantity
        for addon in item.lens_addons.all():
            item_total += addon.price * item.quantity
        subtotal += item_total

    tax_rate = Decimal('0.00')
    tax      = subtotal * tax_rate
    shipping = Decimal('0.00') if subtotal >= Decimal('200.00') else Decimal('20.00')
    total    = subtotal + tax + shipping

    context = {
        'cart':                 cart,
        'cart_items':           cart_items,
        'shipping_addresses':   shipping_addresses,
        'default_shipping':     default_shipping,
        'default_billing':      default_billing,
        'subtotal':             subtotal,
        'tax':                  tax,
        'shipping':             shipping,
        'total':                total,
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'razorpay_key_id':      getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }
    return render(request, 'checkout.html', context)


# ─────────────────────────────────────────────────────────────
# PLACE ORDER
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def place_order(request):
    try:
        cart       = get_or_create_cart(request)
        cart_items = cart.items.all()

        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('cart:cart_view')

        payment_method = request.POST.get('payment_method', '').strip()
        customer_notes = request.POST.get('customer_notes', '')

        # ── Shipping address ──────────────────────────────────
        if request.POST.get('shipping_address_id'):
            shipping_address = get_object_or_404(
                Address, id=request.POST.get('shipping_address_id'), user=request.user
            )
            shipping_info = {
                'line1':        shipping_address.address_line1,
                'line2':        shipping_address.address_line2 or '',
                'city':         shipping_address.city,
                'state':        shipping_address.state or '',
                'country':      shipping_address.country,
                'postal_code':  shipping_address.postal_code or '',
                'phone':        shipping_address.phone or '',
                'name':         shipping_address.full_name,
            }
        else:
            shipping_info = {
                'line1':       request.POST.get('address_line1', ''),
                'line2':       request.POST.get('address_line2', ''),
                'city':        request.POST.get('city', ''),
                'state':       request.POST.get('state', ''),
                'country':     request.POST.get('country', 'Qatar'),
                'postal_code': request.POST.get('postal_code', ''),
                'phone':       request.POST.get('phone', ''),
                'name':        request.POST.get('full_name', request.user.get_full_name()),
            }

        # ── Delivery coordinates (optional) ──────────────────
        delivery_latitude  = request.POST.get('delivery_latitude')  or None
        delivery_longitude = request.POST.get('delivery_longitude') or None

        # ── Billing address ───────────────────────────────────
        billing_same = request.POST.get('same_as_shipping') == 'on'
        if billing_same:
            billing_info = shipping_info.copy()
        elif request.POST.get('billing_address_id'):
            billing_address = get_object_or_404(
                Address, id=request.POST.get('billing_address_id'), user=request.user
            )
            billing_info = {
                'line1':       billing_address.address_line1,
                'line2':       billing_address.address_line2 or '',
                'city':        billing_address.city,
                'state':       billing_address.state or '',
                'country':     billing_address.country,
                'postal_code': billing_address.postal_code or '',
            }
        else:
            billing_info = {
                'line1':       request.POST.get('billing_address_line1', ''),
                'line2':       '',
                'city':        request.POST.get('billing_city', ''),
                'state':       '',
                'country':     request.POST.get('billing_country', 'Qatar'),
                'postal_code': '',
            }

        # ── Calculate totals ──────────────────────────────────
        subtotal = Decimal('0.00')
        for item in cart_items:
            item_total = item.unit_price * item.quantity
            if item.lens_price:
                item_total += item.lens_price * item.quantity
            for addon in item.lens_addons.all():
                item_total += addon.price * item.quantity
            subtotal += item_total

        tax               = Decimal('0.00')
        shipping_amount   = Decimal('0.00') if subtotal >= Decimal('200.00') else Decimal('20.00')
        total             = subtotal + tax + shipping_amount

        # ── Create Order ──────────────────────────────────────
        order = Order.objects.create(
            order_number             = generate_order_number(),
            customer                 = request.user,
            order_type               = 'online',
            status                   = 'pending',
            currency                 = getattr(cart, 'currency', 'QAR'),
            subtotal                 = subtotal,
            tax_amount               = tax,
            shipping_amount          = shipping_amount,
            discount_amount          = Decimal('0.00'),
            total_amount             = total,
            customer_email           = request.user.email,
            customer_phone           = shipping_info['phone'],
            customer_name            = shipping_info['name'],
            shipping_address_line1   = shipping_info['line1'],
            shipping_address_line2   = shipping_info['line2'],
            shipping_city            = shipping_info['city'],
            shipping_state           = shipping_info['state'],
            shipping_country         = shipping_info['country'],
            shipping_postal_code     = shipping_info['postal_code'],
            delivery_latitude        = Decimal(delivery_latitude)  if delivery_latitude  else None,
            delivery_longitude       = Decimal(delivery_longitude) if delivery_longitude else None,
            billing_same_as_shipping = billing_same,
            billing_address_line1    = billing_info['line1'],
            billing_address_line2    = billing_info.get('line2', ''),
            billing_city             = billing_info['city'],
            billing_state            = billing_info.get('state', ''),
            billing_country          = billing_info['country'],
            billing_postal_code      = billing_info.get('postal_code', ''),
            payment_method           = payment_method,
            payment_status           = 'pending',
            customer_notes           = customer_notes,
        )

        # ── Create Order Items ────────────────────────────────
        for cart_item in cart_items:
            item_subtotal = cart_item.unit_price * cart_item.quantity
            if cart_item.lens_price:
                item_subtotal += cart_item.lens_price * cart_item.quantity

            order_item = OrderItem.objects.create(
                order             = order,
                product           = cart_item.product,
                variant           = cart_item.variant,
                product_name      = cart_item.product.name,
                product_sku       = cart_item.product.sku,
                variant_details   = {
                    'color': cart_item.variant.color_name if cart_item.variant else None,
                    'size':  cart_item.variant.size       if cart_item.variant else None,
                },
                quantity                    = cart_item.quantity,
                unit_price                  = cart_item.unit_price,
                requires_prescription       = cart_item.requires_prescription,
                lens_option                 = cart_item.lens_option,
                lens_option_name            = cart_item.lens_option.name if cart_item.lens_option else '',
                lens_price                  = cart_item.lens_price,
                prescription_data           = cart_item.prescription_data,
                contact_lens_left_power     = cart_item.contact_lens_left_power,
                contact_lens_right_power    = cart_item.contact_lens_right_power,
                subtotal                    = item_subtotal,
                special_instructions        = cart_item.special_instructions,
            )

            for addon_item in cart_item.lens_addons.all():
                OrderItemLensAddOn.objects.create(
                    order_item = order_item,
                    addon      = addon_item.addon,
                    addon_name = addon_item.addon.name,
                    price      = addon_item.price,
                )

        # ── Status history ────────────────────────────────────
        OrderStatusHistory.objects.create(
            order      = order,
            to_status  = 'pending',
            notes      = 'Order created',
            changed_by = request.user,
        )

        # ── Route to payment handler ──────────────────────────
        if payment_method == 'cash_on_delivery':
            cart.items.all().delete()
            messages.success(request, 'Order placed successfully! Pay when your order arrives.')
            return redirect('orders:order_confirmation', order_number=order.order_number)

        elif payment_method == 'stripe':
            return redirect('orders:stripe_payment', order_number=order.order_number)

        elif payment_method == 'razorpay':
            return redirect('orders:razorpay_payment', order_number=order.order_number)

        elif payment_method == 'paypal':
            return redirect('orders:paypal_payment', order_number=order.order_number)

        elif payment_method == 'sadad':
            return redirect('orders:sadad_payment', order_number=order.order_number)

        else:
            messages.error(request, f'Unknown payment method: "{payment_method}". Please try again.')
            order.delete()   # roll back the order — user can resubmit
            return redirect('orders:checkout')

    except Exception as e:
        logger.error(f"place_order error: {e}", exc_info=True)
        messages.error(request, f'Error placing order: {str(e)}')
        return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# STRIPE
# ─────────────────────────────────────────────────────────────

@login_required
def stripe_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        result = StripePaymentService.create_payment_intent(order)
        if result['success']:
            order.payment_gateway        = 'stripe'
            order.payment_transaction_id = result['payment_intent_id']
            order.save()
            context = {
                'order':                 order,
                'client_secret':         result['client_secret'],
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            }
            return render(request, 'stripe_payment.html', context)
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    except Exception as e:
        messages.error(request, f'Error initializing Stripe payment: {str(e)}')
        return redirect('orders:checkout')


@login_required
@require_POST
def stripe_payment_confirm(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    try:
        payment_intent_id = request.POST.get('payment_intent_id')
        result = StripePaymentService.confirm_payment(payment_intent_id)

        if result['success']:
            order.payment_status           = 'completed'
            order.payment_gateway_response = result
            order.paid_at                  = timezone.now()
            order.status                   = 'confirmed'
            order.confirmed_at             = timezone.now()
            order.save()

            PaymentTransaction.objects.create(
                order                  = order,
                transaction_id         = generate_transaction_id(),
                gateway_transaction_id = payment_intent_id,
                transaction_type       = 'payment',
                status                 = 'completed',
                amount                 = order.total_amount,
                currency               = order.currency,
                payment_gateway        = 'stripe',
                payment_method         = 'card',
                gateway_response       = result,
                completed_at           = timezone.now(),
            )

            cart = get_or_create_cart(request)
            cart.items.all().delete()

            OrderStatusHistory.objects.create(
                order       = order,
                from_status = 'pending',
                to_status   = 'confirmed',
                notes       = 'Payment confirmed via Stripe',
                changed_by  = request.user,
            )

            return JsonResponse({
                'success':      True,
                'redirect_url': reverse('orders:order_confirmation', args=[order.order_number]),
            })
        else:
            return JsonResponse({'success': False, 'error': result.get('error')})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────
# RAZORPAY
# ─────────────────────────────────────────────────────────────

@login_required
def razorpay_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        result = RazorpayPaymentService.create_order(order)
        if result['success']:
            order.payment_gateway        = 'razorpay'
            order.payment_transaction_id = result['razorpay_order_id']
            order.save()
            context = {
                'order':              order,
                'razorpay_order_id':  result['razorpay_order_id'],
                'razorpay_key_id':    result['key_id'],
                'amount':             result['amount'],
                'currency':           result['currency'],
            }
            return render(request, 'razorpay_payment.html', context)
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    except Exception as e:
        messages.error(request, f'Error initializing Razorpay payment: {str(e)}')
        return redirect('orders:checkout')


@csrf_exempt
@require_POST
def razorpay_payment_verify(request):
    try:
        data = json.loads(request.body)

        razorpay_order_id   = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature  = data.get('razorpay_signature')

        order = Order.objects.get(payment_transaction_id=razorpay_order_id)

        result = RazorpayPaymentService.verify_payment(
            razorpay_order_id, razorpay_payment_id, razorpay_signature
        )

        if result['success']:
            order.payment_status           = 'completed'
            order.payment_gateway_response = result
            order.paid_at                  = timezone.now()
            order.status                   = 'confirmed'
            order.confirmed_at             = timezone.now()
            order.save()

            PaymentTransaction.objects.create(
                order                  = order,
                transaction_id         = generate_transaction_id(),
                gateway_transaction_id = razorpay_payment_id,
                transaction_type       = 'payment',
                status                 = 'completed',
                amount                 = order.total_amount,
                currency               = order.currency,
                payment_gateway        = 'razorpay',
                payment_method         = result.get('method', 'card'),
                card_last4             = result.get('card_last4', ''),
                card_brand             = result.get('card_network', ''),
                gateway_response       = result,
                completed_at           = timezone.now(),
            )

            cart = Cart.objects.filter(customer=order.customer).first()
            if cart:
                cart.items.all().delete()

            OrderStatusHistory.objects.create(
                order       = order,
                from_status = 'pending',
                to_status   = 'confirmed',
                notes       = 'Payment confirmed via Razorpay',
                changed_by  = order.customer,
            )

            return JsonResponse({
                'success':      True,
                'redirect_url': reverse('orders:order_confirmation', args=[order.order_number]),
            })
        else:
            order.payment_status = 'failed'
            order.save()
            return JsonResponse({'success': False, 'error': result.get('error')})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────
# PAYPAL
# ─────────────────────────────────────────────────────────────

@login_required
def paypal_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        return_url = request.build_absolute_uri(
            reverse('orders:paypal_execute', args=[order.order_number])
        )
        cancel_url = request.build_absolute_uri(reverse('orders:checkout'))

        result = PayPalPaymentService.create_payment(order, return_url, cancel_url)

        if result['success']:
            order.payment_gateway        = 'paypal'
            order.payment_transaction_id = result['payment_id']
            order.save()
            return redirect(result['approval_url'])
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    except Exception as e:
        messages.error(request, f'Error initializing PayPal payment: {str(e)}')
        return redirect('orders:checkout')


@login_required
def paypal_execute(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    try:
        payment_id = request.GET.get('paymentId')
        payer_id   = request.GET.get('PayerID')

        if not payment_id or not payer_id:
            messages.error(request, 'Payment cancelled or invalid.')
            return redirect('orders:checkout')

        result = PayPalPaymentService.execute_payment(payment_id, payer_id)

        if result['success']:
            order.payment_status           = 'completed'
            order.payment_gateway_response = result
            order.paid_at                  = timezone.now()
            order.status                   = 'confirmed'
            order.confirmed_at             = timezone.now()
            order.save()

            PaymentTransaction.objects.create(
                order                  = order,
                transaction_id         = generate_transaction_id(),
                gateway_transaction_id = payment_id,
                transaction_type       = 'payment',
                status                 = 'completed',
                amount                 = order.total_amount,
                currency               = order.currency,
                payment_gateway        = 'paypal',
                payment_method         = 'paypal',
                gateway_response       = result,
                completed_at           = timezone.now(),
            )

            cart = get_or_create_cart(request)
            cart.items.all().delete()

            OrderStatusHistory.objects.create(
                order       = order,
                from_status = 'pending',
                to_status   = 'confirmed',
                notes       = 'Payment confirmed via PayPal',
                changed_by  = request.user,
            )

            messages.success(request, 'Payment successful!')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        else:
            messages.error(request, f"Payment failed: {result.get('error')}")
            return redirect('orders:checkout')
    except Exception as e:
        messages.error(request, f'Error processing PayPal payment: {str(e)}')
        return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# SADAD  (Qatar)
# ─────────────────────────────────────────────────────────────

@login_required
def sadad_payment(request, order_number):
    """
    Renders a hidden auto-submit HTML form that POSTs the customer directly
    to Sadad's hosted checkout page (Web Checkout 2.1).
    No REST API call is made here — the form IS the payment initiation.
    """
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        form_data = SadadPaymentService.build_payment_form_data(order)

        # Store that we're attempting Sadad payment
        order.payment_gateway = 'sadad'
        # Store the order_number as the reference (it becomes ORDERID in Sadad callback)
        order.payment_transaction_id = order.order_number
        order.save()

        context = {
            'order':       order,
            'action_url':  form_data['action_url'],
            'form_fields': form_data['fields'],
        }
        return render(request, 'orders/sadad_redirect.html', context)

    except SadadPaymentError as e:
        logger.error(f"Sadad config error: {e}")
        messages.error(request, str(e))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"sadad_payment view error: {e}", exc_info=True)
        messages.error(request, f'Error initializing Sadad payment: {str(e)}')
        return redirect('orders:checkout')


@csrf_exempt    
def sadad_payment_return(request):
    """
    Sadad POSTs the payment result to CALLBACK_URL after payment.
    Verify the checksumhash, then update the order.

    NOTE: Sadad sends POST (not GET) to the callback URL.
          We accept both just in case.
    """
    if request.method == 'POST':
        post_data = request.POST.dict()
    else:
        post_data = request.GET.dict()

    logger.info(f"Sadad callback received: {post_data}")

    order_id = post_data.get('ORDERID', '')

    if not order_id:
        messages.error(request, 'Invalid payment callback. No order reference received.')
        return redirect('orders:order_list')

    try:
        order = Order.objects.filter(order_number=order_id).first()

        if not order:
            logger.error(f"Sadad callback: order not found for ORDERID={order_id}")
            messages.error(request, 'Order not found.')
            return redirect('orders:order_list')

        if order.payment_status == 'completed':
            return redirect('orders:order_confirmation', order_number=order.order_number)

        # Verify the checksum and payment status
        verify_result = SadadPaymentService.verify_callback(post_data)

        if verify_result['paid']:
            _mark_order_paid_sadad(order, verify_result)
            messages.success(request, '✅ Payment successful! Your order is confirmed.')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        else:
            # Payment failed or checksum invalid
            order.payment_status           = 'failed'
            order.payment_gateway_response = post_data
            order.save()

            resp_msg = verify_result.get('resp_msg', '')
            if not verify_result['checksum_valid']:
                resp_msg = 'Security verification failed. Please contact support.'

            messages.error(
                request,
                f"Payment was not completed. {resp_msg} "
                "Please try again or choose a different payment method."
            )
            return redirect('orders:checkout')

    except Exception as e:
        logger.error(f"sadad_payment_return error: {e}", exc_info=True)
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('orders:order_list')

@csrf_exempt
@require_POST
def sadad_webhook(request):
    """
    Optional: Sadad server-to-server webhook for payment events.
    Configure webhook URL in panel.sadad.qa → Webhook Settings.
    """
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST.dict()

        logger.info(f"Sadad webhook received: {data}")

        order_id       = str(data.get('ORDERID') or data.get('invoiceId') or data.get('id', ''))
        resp_code      = str(data.get('RESPCODE', ''))
        transaction_id = str(data.get('transaction_number') or data.get('transactionId', ''))

        if not order_id:
            return HttpResponse("Missing ORDERID", status=400)

        try:
            order = Order.objects.get(order_number=order_id)
        except Order.DoesNotExist:
            logger.warning(f"Sadad webhook: order not found for ORDERID={order_id}")
            return HttpResponse("Order not found", status=404)

        if resp_code == '1' and order.payment_status != 'completed':
            verify_result = {
                'paid':           True,
                'checksum_valid': True,
                'resp_code':      resp_code,
                'resp_msg':       data.get('RESPMSG', ''),
                'order_id':       order_id,
                'transaction_id': transaction_id,
                'amount':         str(data.get('TXNAMOUNT', '')),
                'raw':            data,
            }
            _mark_order_paid_sadad(order, verify_result)
            logger.info(f"Sadad webhook: order {order.order_number} marked PAID")

        elif resp_code not in ('', '1') and order.payment_status not in ('completed', 'failed'):
            order.payment_status           = 'failed'
            order.payment_gateway_response = data
            order.save()
            logger.info(f"Sadad webhook: order {order.order_number} marked FAILED (RESPCODE={resp_code})")

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Sadad webhook error: {e}", exc_info=True)
        return HttpResponse("Internal error", status=500)


# ─────────────────────────────────────────────────────────────
# SADAD HELPERS
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def _mark_order_paid_sadad(order, verify_result: dict):
    """Mark order as paid after confirmed Sadad payment."""
    order.payment_status           = 'completed'
    order.payment_gateway_response = verify_result.get('raw', verify_result)
    order.paid_at                  = timezone.now()
    order.status                   = 'confirmed'
    order.confirmed_at             = timezone.now()
    order.save()

    PaymentTransaction.objects.get_or_create(
        order                  = order,
        gateway_transaction_id = verify_result.get('transaction_id', order.order_number),
        defaults=dict(
            transaction_id         = generate_transaction_id(),
            transaction_type       = 'payment',
            status                 = 'completed',
            amount                 = order.total_amount,
            currency               = order.currency,
            payment_gateway        = 'sadad',
            payment_method         = 'sadad',
            gateway_response       = verify_result.get('raw', verify_result),
            completed_at           = timezone.now(),
        )
    )

    # Clear the cart
    cart = Cart.objects.filter(customer=order.customer).first()
    if cart:
        cart.items.all().delete()

    OrderStatusHistory.objects.create(
        order       = order,
        from_status = 'pending',
        to_status   = 'confirmed',
        notes       = f"Payment confirmed via Sadad (txn: {verify_result.get('transaction_id', '')})",
        changed_by  = order.customer,
    )



@transaction.atomic
def _mark_order_paid_webhook(order, verify_result: dict):
    """Same as above but called from webhook (no request object)."""
    order.payment_status           = 'completed'
    order.payment_gateway_response = verify_result.get('raw', verify_result)
    order.paid_at                  = timezone.now()
    order.status                   = 'confirmed'
    order.confirmed_at             = timezone.now()
    order.save()

    PaymentTransaction.objects.create(
        order                  = order,
        transaction_id         = generate_transaction_id(),
        gateway_transaction_id = verify_result.get('transaction_id', ''),
        transaction_type       = 'payment',
        status                 = 'completed',
        amount                 = order.total_amount,
        currency               = order.currency,
        payment_gateway        = 'sadad',
        payment_method         = 'sadad',
        gateway_response       = verify_result.get('raw', verify_result),
        completed_at           = timezone.now(),
    )

    cart = Cart.objects.filter(customer=order.customer).first()
    if cart:
        cart.items.all().delete()

    OrderStatusHistory.objects.create(
        order       = order,
        from_status = 'pending',
        to_status   = 'confirmed',
        notes       = 'Payment confirmed via Sadad (webhook)',
        changed_by  = order.customer,
    )


# ─────────────────────────────────────────────────────────────
# ORDER MANAGEMENT
# ─────────────────────────────────────────────────────────────

@login_required
def order_confirmation(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'orders/order_confirmation.html', {'order': order})


@login_required
def order_list(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)

    context = {
        'orders':         orders,
        'status_filter':  status_filter,
        'order_statuses': Order.ORDER_STATUS,
    }
    return render(request, 'order_list.html', context)


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    order_items          = order.items.select_related('product', 'variant', 'lens_option').prefetch_related('lens_addons')
    status_history       = order.status_history.all()
    payment_transactions = order.payment_transactions.all()

    context = {
        'order':                order,
        'order_items':          order_items,
        'status_history':       status_history,
        'payment_transactions': payment_transactions,
    }
    return render(request, 'order_detail.html', context)


@login_required
def track_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    status_history     = order.status_history.all()
    status_progression = ['pending', 'confirmed', 'processing', 'shipped', 'delivered']
    current_index      = status_progression.index(order.status) if order.status in status_progression else 0

    context = {
        'order':                order,
        'status_history':       status_history,
        'status_progression':   status_progression,
        'current_status_index': current_index,
    }
    return render(request, 'track_order.html', context)


@login_required
@require_POST
def cancel_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect('orders:order_detail', order_number=order_number)

    old_status   = order.status
    order.status = 'cancelled'
    order.save()

    OrderStatusHistory.objects.create(
        order       = order,
        from_status = old_status,
        to_status   = 'cancelled',
        notes       = 'Cancelled by customer',
        changed_by  = request.user,
    )

    messages.success(request, 'Order cancelled successfully.')
    return redirect('orders:order_detail', order_number=order_number)


@login_required
def get_order_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return JsonResponse({
        'order_number':    order.order_number,
        'status':          order.status,
        'status_display':  order.get_status_display(),
        'payment_status':  order.payment_status,
        'tracking_number': order.tracking_number,
        'carrier':         order.carrier,
    })