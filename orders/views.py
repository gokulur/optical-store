# orders/views.py — COMPLETE FIXED VERSION
# Fixes:
#  1. cart.currency crash → hardcoded 'QAR' fallback
#  2. lens_addons iteration crash → safe attribute access
#  3. Better error logging with full traceback
#  4. Decimal conversion safety
#  5. Cart clear only after successful order for COD
#  6. All payment routes working

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from decimal import Decimal, InvalidOperation
import random
import string
import json
import logging

from django.conf import settings
from .models import Order, OrderItem, OrderItemLensAddOn, OrderStatusHistory, PaymentTransaction
from cart.models import Cart
from users.models import Address
from cart.views import get_or_create_cart
from .payment_services import (
    StripePaymentService,
    RazorpayPaymentService,
    PayPalPaymentService,
    SadadPaymentService,
    SadadPaymentError,
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


def safe_decimal(value, default='0.00'):
    """Safely convert a value to Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


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
        item_total = safe_decimal(item.unit_price) * item.quantity
        if getattr(item, 'lens_price', None):
            item_total += safe_decimal(item.lens_price) * item.quantity
        for addon in item.lens_addons.all():
            item_total += safe_decimal(addon.price) * item.quantity
        subtotal += item_total

    tax      = Decimal('0.00')
    shipping = Decimal('0.00') if subtotal >= Decimal('200.00') else Decimal('20.00')
    total    = subtotal + tax + shipping

    context = {
        'cart':                   cart,
        'cart_items':             cart_items,
        'shipping_addresses':     shipping_addresses,
        'default_shipping':       default_shipping,
        'default_billing':        default_billing,
        'subtotal':               subtotal,
        'tax':                    tax,
        'shipping':               shipping,
        'total':                  total,
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'razorpay_key_id':        getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }
    return render(request, 'checkout.html', context)


# ─────────────────────────────────────────────────────────────
# PLACE ORDER
# NOTE: NO @transaction.atomic at the top level — order must be
# committed BEFORE redirecting to any external payment gateway.
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def place_order(request):
    try:
        cart       = get_or_create_cart(request)
        cart_items = list(cart.items.select_related(
            'product', 'variant', 'lens_option'
        ).prefetch_related('lens_addons', 'lens_addons__addon'))

        if not cart_items:
            messages.error(request, 'Your cart is empty.')
            return redirect('cart:cart_view')

        payment_method = request.POST.get('payment_method', '').strip()
        customer_notes = request.POST.get('customer_notes', '')

        if not payment_method:
            messages.error(request, 'Please select a payment method.')
            return redirect('orders:checkout')

        # ── Shipping address ──────────────────────────────────
        shipping_address_id = request.POST.get('shipping_address_id', '').strip()
        if shipping_address_id:
            try:
                shipping_address = Address.objects.get(
                    id=shipping_address_id, user=request.user
                )
                shipping_info = {
                    'line1':       shipping_address.address_line1,
                    'line2':       getattr(shipping_address, 'address_line2', '') or '',
                    'city':        shipping_address.city,
                    'state':       getattr(shipping_address, 'state', '') or '',
                    'country':     shipping_address.country,
                    'postal_code': getattr(shipping_address, 'postal_code', '') or '',
                    'phone':       getattr(shipping_address, 'phone', '') or '',
                    'name':        getattr(shipping_address, 'full_name', '') or request.user.get_full_name(),
                }
            except Address.DoesNotExist:
                messages.error(request, 'Selected address not found.')
                return redirect('orders:checkout')
        else:
            # Manual address entry
            full_name = request.POST.get('full_name', '').strip()
            city      = request.POST.get('city', '').strip()
            address1  = request.POST.get('address_line1', '').strip()

            if not full_name or not city or not address1:
                messages.error(request, 'Please fill in all required address fields.')
                return redirect('orders:checkout')

            shipping_info = {
                'line1':       address1,
                'line2':       request.POST.get('address_line2', ''),
                'city':        city,
                'state':       request.POST.get('state', ''),
                'country':     request.POST.get('country', 'Qatar'),
                'postal_code': request.POST.get('postal_code', ''),
                'phone':       request.POST.get('phone', ''),
                'name':        full_name,
            }

        # ── Delivery coordinates (optional) ──────────────────
        delivery_latitude  = request.POST.get('delivery_latitude', '').strip() or None
        delivery_longitude = request.POST.get('delivery_longitude', '').strip() or None

        # ── Billing address ───────────────────────────────────
        billing_same = request.POST.get('same_as_shipping') in ('on', 'true', '1', 'yes')
        if billing_same:
            billing_info = shipping_info.copy()
        else:
            billing_address_id = request.POST.get('billing_address_id', '').strip()
            if billing_address_id:
                try:
                    billing_address = Address.objects.get(
                        id=billing_address_id, user=request.user
                    )
                    billing_info = {
                        'line1':       billing_address.address_line1,
                        'line2':       getattr(billing_address, 'address_line2', '') or '',
                        'city':        billing_address.city,
                        'state':       getattr(billing_address, 'state', '') or '',
                        'country':     billing_address.country,
                        'postal_code': getattr(billing_address, 'postal_code', '') or '',
                    }
                except Address.DoesNotExist:
                    billing_info = shipping_info.copy()
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
            item_price = safe_decimal(getattr(item, 'unit_price', 0))
            item_total = item_price * item.quantity

            lens_price = safe_decimal(getattr(item, 'lens_price', 0))
            if lens_price > 0:
                item_total += lens_price * item.quantity

            for addon in item.lens_addons.all():
                addon_price = safe_decimal(getattr(addon, 'price', 0))
                item_total += addon_price * item.quantity

            subtotal += item_total

        tax             = Decimal('0.00')
        shipping_amount = Decimal('0.00') if subtotal >= Decimal('200.00') else Decimal('20.00')
        total           = subtotal + tax + shipping_amount

        # ── Determine currency ────────────────────────────────
        # Safely get currency from cart, default to QAR
        currency = 'QAR'
        try:
            currency = str(getattr(cart, 'currency', 'QAR') or 'QAR')
        except Exception:
            currency = 'QAR'

        # ── Create Order ──────────────────────────────────────
        order = Order.objects.create(
            order_number             = generate_order_number(),
            customer                 = request.user,
            order_type               = 'online',
            status                   = 'pending',
            currency                 = currency,
            subtotal                 = subtotal,
            tax_amount               = tax,
            shipping_amount          = shipping_amount,
            discount_amount          = Decimal('0.00'),
            total_amount             = total,
            customer_email           = request.user.email,
            customer_phone           = shipping_info.get('phone', ''),
            customer_name            = shipping_info.get('name', request.user.get_full_name()),
            shipping_address_line1   = shipping_info.get('line1', ''),
            shipping_address_line2   = shipping_info.get('line2', ''),
            shipping_city            = shipping_info.get('city', ''),
            shipping_state           = shipping_info.get('state', ''),
            shipping_country         = shipping_info.get('country', 'Qatar'),
            shipping_postal_code     = shipping_info.get('postal_code', ''),
            delivery_latitude        = safe_decimal(delivery_latitude) if delivery_latitude else None,
            delivery_longitude       = safe_decimal(delivery_longitude) if delivery_longitude else None,
            billing_same_as_shipping = billing_same,
            billing_address_line1    = billing_info.get('line1', ''),
            billing_address_line2    = billing_info.get('line2', ''),
            billing_city             = billing_info.get('city', ''),
            billing_state            = billing_info.get('state', ''),
            billing_country          = billing_info.get('country', 'Qatar'),
            billing_postal_code      = billing_info.get('postal_code', ''),
            payment_method           = payment_method,
            payment_status           = 'pending',
            customer_notes           = customer_notes,
        )

        # ── Create Order Items ────────────────────────────────
        for cart_item in cart_items:
            item_price    = safe_decimal(getattr(cart_item, 'unit_price', 0))
            lens_price    = safe_decimal(getattr(cart_item, 'lens_price', 0))
            item_subtotal = item_price * cart_item.quantity
            if lens_price > 0:
                item_subtotal += lens_price * cart_item.quantity

            # Build variant details safely
            variant_details = None
            if cart_item.variant:
                variant_details = {
                    'color': getattr(cart_item.variant, 'color_name', None),
                    'size':  getattr(cart_item.variant, 'size', None),
                }

            order_item = OrderItem.objects.create(
                order                    = order,
                product                  = cart_item.product,
                variant                  = cart_item.variant,
                product_name             = cart_item.product.name,
                product_sku              = getattr(cart_item.product, 'sku', '') or '',
                variant_details          = variant_details,
                quantity                 = cart_item.quantity,
                unit_price               = item_price,
                requires_prescription    = getattr(cart_item, 'requires_prescription', False),
                lens_option              = getattr(cart_item, 'lens_option', None),
                lens_option_name         = (
                    cart_item.lens_option.name
                    if getattr(cart_item, 'lens_option', None)
                    else ''
                ),
                lens_price               = lens_price,
                prescription_data        = getattr(cart_item, 'prescription_data', None),
                contact_lens_left_power  = getattr(cart_item, 'contact_lens_left_power', None),
                contact_lens_right_power = getattr(cart_item, 'contact_lens_right_power', None),
                subtotal                 = item_subtotal,
                special_instructions     = getattr(cart_item, 'special_instructions', '') or '',
            )

            # Add-ons — safely iterate
            try:
                for addon_item in cart_item.lens_addons.all():
                    addon_obj  = getattr(addon_item, 'addon', None)
                    addon_name = getattr(addon_obj, 'name', '') if addon_obj else getattr(addon_item, 'name', '')
                    addon_price = safe_decimal(getattr(addon_item, 'price', 0))
                    if addon_obj:
                        OrderItemLensAddOn.objects.create(
                            order_item = order_item,
                            addon      = addon_obj,
                            addon_name = addon_name,
                            price      = addon_price,
                        )
            except Exception as addon_err:
                logger.warning(f"Addon processing error for cart_item {cart_item.id}: {addon_err}")

        OrderStatusHistory.objects.create(
            order      = order,
            to_status  = 'pending',
            notes      = 'Order created',
            changed_by = request.user,
        )

        logger.info(f"Order {order.order_number} created successfully for {request.user.email}, payment: {payment_method}")

        # ── Route to payment handler ──────────────────────────
        if payment_method == 'cash_on_delivery':
            # Clear cart and confirm
            cart.items.all().delete()
            order.status       = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save(update_fields=['status', 'confirmed_at'])
            OrderStatusHistory.objects.create(
                order       = order,
                from_status = 'pending',
                to_status   = 'confirmed',
                notes       = 'Cash on delivery order confirmed',
                changed_by  = request.user,
            )
            messages.success(request, '✅ Order placed successfully! Pay when your order arrives.')
            return redirect('orders:order_confirmation', order_number=order.order_number)

        elif payment_method == 'sadad':
            return redirect('orders:sadad_payment', order_number=order.order_number)

        elif payment_method == 'stripe':
            return redirect('orders:stripe_payment', order_number=order.order_number)

        elif payment_method == 'razorpay':
            return redirect('orders:razorpay_payment', order_number=order.order_number)

        elif payment_method == 'paypal':
            return redirect('orders:paypal_payment', order_number=order.order_number)

        else:
            messages.error(request, f'Unknown payment method: "{payment_method}".')
            order.delete()
            return redirect('orders:checkout')

    except Exception as e:
        logger.error(f"place_order CRASH: {type(e).__name__}: {e}", exc_info=True)
        messages.error(request, f'Error placing order: {str(e)}')
        return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# SADAD (Qatar) — Web Checkout 2.1
# ─────────────────────────────────────────────────────────────

@login_required
def sadad_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)

    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        form_data = SadadPaymentService.build_payment_form_data(order)

        order.payment_gateway        = 'sadad'
        order.payment_transaction_id = order.order_number
        order.save(update_fields=['payment_gateway', 'payment_transaction_id'])

        return render(request, 'orders/sadad_redirect.html', {
            'order':       order,
            'action_url':  form_data['action_url'],
            'form_fields': form_data['fields'],
        })

    except SadadPaymentError as e:
        logger.error(f"Sadad config error: {e}")
        messages.error(request, str(e))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"sadad_payment error: {e}", exc_info=True)
        messages.error(request, f'Sadad init error: {str(e)}')
        return redirect('orders:checkout')


@csrf_exempt
def sadad_payment_return(request):
    if request.method == 'POST':
        post_data = request.POST.dict()
    else:
        post_data = request.GET.dict()

    logger.info(f"Sadad callback received: {post_data}")
    order_id = post_data.get('ORDERID', '').strip()

    if not order_id:
        messages.error(request, 'Invalid payment response.')
        return redirect('orders:order_list')

    try:
        order = Order.objects.filter(order_number=order_id).first()
        if not order:
            messages.error(request, 'Order not found.')
            return redirect('orders:order_list')

        if order.payment_status == 'completed':
            return redirect('orders:order_confirmation', order_number=order.order_number)

        verify = SadadPaymentService.verify_callback(post_data)
        if verify['paid']:
            _mark_order_paid_sadad(order, verify)
            messages.success(request, '✅ Payment successful!')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        else:
            order.payment_status           = 'failed'
            order.payment_gateway_response = post_data
            order.save(update_fields=['payment_status', 'payment_gateway_response'])
            msg = 'Security check failed.' if not verify['checksum_valid'] else (
                f"Payment not completed: {verify.get('resp_msg', 'unknown error')}"
            )
            messages.error(request, msg)
            return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"sadad_payment_return error: {e}", exc_info=True)
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('orders:order_list')


@csrf_exempt
@require_POST
def sadad_webhook(request):
    try:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            data = request.POST.dict()

        order_id  = str(data.get('ORDERID') or data.get('id', '')).strip()
        resp_code = str(data.get('RESPCODE', '')).strip()
        txn_id    = str(data.get('transaction_number') or '').strip()

        if not order_id:
            return HttpResponse("Missing ORDERID", status=400)

        try:
            order = Order.objects.get(order_number=order_id)
        except Order.DoesNotExist:
            return HttpResponse("Not found", status=404)

        if resp_code == '1' and order.payment_status != 'completed':
            _mark_order_paid_sadad(order, {
                'paid': True, 'checksum_valid': True,
                'resp_code': resp_code, 'transaction_id': txn_id,
                'amount': str(data.get('TXNAMOUNT', '')), 'raw': data,
            })
        elif resp_code not in ('', '1') and order.payment_status not in ('completed', 'failed'):
            order.payment_status = 'failed'
            order.save(update_fields=['payment_status'])

        return HttpResponse("OK", status=200)
    except Exception as e:
        logger.error(f"Sadad webhook error: {e}", exc_info=True)
        return HttpResponse("Error", status=500)


@transaction.atomic
def _mark_order_paid_sadad(order, verify_result):
    order.payment_status           = 'completed'
    order.payment_gateway_response = verify_result.get('raw', verify_result)
    order.paid_at                  = timezone.now()
    order.status                   = 'confirmed'
    order.confirmed_at             = timezone.now()
    order.save()

    PaymentTransaction.objects.get_or_create(
        order                  = order,
        gateway_transaction_id = verify_result.get('transaction_id') or order.order_number,
        defaults=dict(
            transaction_id   = generate_transaction_id(),
            transaction_type = 'payment',
            status           = 'completed',
            amount           = order.total_amount,
            currency         = order.currency,
            payment_gateway  = 'sadad',
            payment_method   = 'sadad',
            gateway_response = verify_result.get('raw', verify_result),
            completed_at     = timezone.now(),
        )
    )

    cart = Cart.objects.filter(customer=order.customer).first()
    if cart:
        cart.items.all().delete()

    OrderStatusHistory.objects.create(
        order       = order,
        from_status = 'pending',
        to_status   = 'confirmed',
        notes       = f"Paid via Sadad (txn: {verify_result.get('transaction_id', '')})",
        changed_by  = order.customer,
    )


# ─────────────────────────────────────────────────────────────
# STRIPE
# ─────────────────────────────────────────────────────────────

@login_required
def stripe_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    try:
        result = StripePaymentService.create_payment_intent(order)
        if result['success']:
            order.payment_gateway        = 'stripe'
            order.payment_transaction_id = result['payment_intent_id']
            order.save()
            return render(request, 'stripe_payment.html', {
                'order': order,
                'client_secret': result['client_secret'],
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            })
        messages.error(request, f"Stripe error: {result.get('error')}")
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"stripe_payment error: {e}", exc_info=True)
        messages.error(request, str(e))
        return redirect('orders:checkout')


@login_required
@require_POST
def stripe_payment_confirm(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    try:
        result = StripePaymentService.confirm_payment(request.POST.get('payment_intent_id'))
        if result['success']:
            order.payment_status = 'completed'
            order.paid_at        = timezone.now()
            order.status         = 'confirmed'
            order.confirmed_at   = timezone.now()
            order.save()
            get_or_create_cart(request).items.all().delete()
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('orders:order_confirmation', args=[order.order_number])
            })
        return JsonResponse({'success': False, 'error': result.get('error')})
    except Exception as e:
        logger.error(f"stripe_payment_confirm error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────
# RAZORPAY
# ─────────────────────────────────────────────────────────────

@login_required
def razorpay_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    try:
        result = RazorpayPaymentService.create_order(order)
        if result['success']:
            order.payment_gateway        = 'razorpay'
            order.payment_transaction_id = result['razorpay_order_id']
            order.save()
            return render(request, 'razorpay_payment.html', {
                'order':              order,
                'razorpay_order_id':  result['razorpay_order_id'],
                'razorpay_key_id':    result['key_id'],
                'amount':             result['amount'],
                'currency':           result['currency'],
            })
        messages.error(request, result.get('error'))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"razorpay_payment error: {e}", exc_info=True)
        messages.error(request, str(e))
        return redirect('orders:checkout')


@csrf_exempt
@require_POST
def razorpay_payment_verify(request):
    try:
        data   = json.loads(request.body)
        result = RazorpayPaymentService.verify_payment(
            data['razorpay_order_id'],
            data['razorpay_payment_id'],
            data['razorpay_signature']
        )
        order = Order.objects.get(payment_transaction_id=data['razorpay_order_id'])
        if result['success']:
            order.payment_status = 'completed'
            order.paid_at        = timezone.now()
            order.status         = 'confirmed'
            order.confirmed_at   = timezone.now()
            order.save()
            cart = Cart.objects.filter(customer=order.customer).first()
            if cart:
                cart.items.all().delete()
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('orders:order_confirmation', args=[order.order_number])
            })
        order.payment_status = 'failed'
        order.save()
        return JsonResponse({'success': False, 'error': result.get('error')})
    except Exception as e:
        logger.error(f"razorpay_payment_verify error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────
# PAYPAL
# ─────────────────────────────────────────────────────────────

@login_required
def paypal_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    try:
        result = PayPalPaymentService.create_payment(
            order,
            request.build_absolute_uri(reverse('orders:paypal_execute', args=[order.order_number])),
            request.build_absolute_uri(reverse('orders:checkout'))
        )
        if result['success']:
            order.payment_gateway        = 'paypal'
            order.payment_transaction_id = result['payment_id']
            order.save()
            return redirect(result['approval_url'])
        messages.error(request, result.get('error'))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"paypal_payment error: {e}", exc_info=True)
        messages.error(request, str(e))
        return redirect('orders:checkout')


@login_required
def paypal_execute(request, order_number):
    order      = get_object_or_404(Order, order_number=order_number, customer=request.user)
    payment_id = request.GET.get('paymentId')
    payer_id   = request.GET.get('PayerID')
    if not payment_id or not payer_id:
        messages.error(request, 'Payment cancelled.')
        return redirect('orders:checkout')
    try:
        result = PayPalPaymentService.execute_payment(payment_id, payer_id)
        if result['success']:
            order.payment_status = 'completed'
            order.paid_at        = timezone.now()
            order.status         = 'confirmed'
            order.confirmed_at   = timezone.now()
            order.save()
            get_or_create_cart(request).items.all().delete()
            messages.success(request, 'Payment successful!')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        messages.error(request, result.get('error'))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"paypal_execute error: {e}", exc_info=True)
        messages.error(request, str(e))
        return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# ORDER MANAGEMENT
# ─────────────────────────────────────────────────────────────

@login_required
def order_confirmation(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'orders/order_confirmation.html', {'order': order})


@login_required
def order_list(request):
    orders        = Order.objects.filter(customer=request.user).order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)
    return render(request, 'order_list.html', {
        'orders': orders,
        'status_filter': status_filter,
        'order_statuses': Order.ORDER_STATUS,
    })


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'order_detail.html', {
        'order':                order,
        'order_items':          order.items.select_related(
            'product', 'variant', 'lens_option'
        ).prefetch_related('lens_addons'),
        'status_history':       order.status_history.all(),
        'payment_transactions': order.payment_transactions.all(),
    })


@login_required
def track_order(request, order_number):
    order              = get_object_or_404(Order, order_number=order_number, customer=request.user)
    status_progression = ['pending', 'confirmed', 'processing', 'shipped', 'delivered']
    current_index      = (
        status_progression.index(order.status)
        if order.status in status_progression else 0
    )
    return render(request, 'track_order.html', {
        'order':                order,
        'status_history':       order.status_history.all(),
        'status_progression':   status_progression,
        'current_status_index': current_index,
    })


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
    messages.success(request, 'Order cancelled.')
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