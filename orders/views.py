# orders/views.py
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
import random, string, json, logging, re

from django.conf import settings
from .models import Order, OrderItem, OrderItemLensAddOn, OrderStatusHistory, PaymentTransaction
from cart.models import Cart
from users.models import Address
from cart.views import get_or_create_cart
from .payment_services import (
    SadadPaymentService, SadadPaymentError,
    StripePaymentService, RazorpayPaymentService, PayPalPaymentService,
    PaymentGatewayError,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _gen_order_number():
    ts  = timezone.now().strftime('%Y%m%d')
    rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{ts}-{rnd}"

def _gen_txn_id():
    ts  = timezone.now().strftime('%Y%m%d%H%M%S')
    rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"TXN-{ts}-{rnd}"

def _dec(v, default='0.00'):
    try:
        return Decimal(str(v)) if v not in (None, '') else Decimal(default)
    except Exception:
        return Decimal(default)

def _calc_totals(cart_items):
    subtotal = Decimal('0.00')
    for item in cart_items:
        line = _dec(getattr(item, 'unit_price', 0)) * item.quantity
        lp   = _dec(getattr(item, 'lens_price', 0))
        if lp > 0:
            line += lp * item.quantity
        try:
            for a in item.lens_addons.all():
                line += _dec(getattr(a, 'price', 0)) * item.quantity
        except Exception:
            pass
        subtotal += line
    tax      = Decimal('0.00')
    shipping = Decimal('0.00') if subtotal >= Decimal('200.00') else Decimal('20.00')
    return subtotal, tax, shipping, subtotal + tax + shipping


# ─────────────────────────────────────────────────────────────
# CHECKOUT
# ─────────────────────────────────────────────────────────────

@login_required
def checkout(request):
    buy_now_data = request.session.get('buy_now') if request.GET.get('buy_now') else None

    if buy_now_data:
        from catalog.models import Product as CatalogProduct
        try:
            product = CatalogProduct.objects.get(id=buy_now_data['product_id'], is_active=True)
            qty = buy_now_data['quantity']
            
            class _BuyNowItem:
                def __init__(self, p, q):
                    self.product = p
                    self.quantity = q
                    self.unit_price = p.base_price
                    self.lens_price = Decimal('0.00')
                    def _empty(): return []
                    class _LensAddons:
                        def all(self): return []
                    self.lens_addons = _LensAddons()

            cart_items = [_BuyNowItem(product, qty)]
            sub = product.base_price * qty
            tax = Decimal('0.00')
            ship = Decimal('0.00') if sub >= Decimal('200.00') else Decimal('20.00')
            total = sub + tax + ship
            addrs = request.user.addresses.all()
            return render(request, 'checkout.html', {
                'cart_items': cart_items,
                'shipping_addresses': addrs,
                'default_shipping': addrs.filter(is_default_shipping=True).first(),
                'default_billing': addrs.filter(is_default_billing=True).first(),
                'subtotal': sub, 'tax': tax, 'shipping': ship, 'total': total,
                'is_buy_now': True,
            })
        except Exception:
            pass  # fall through to normal cart

    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'variant', 'lens_option').prefetch_related('lens_addons')
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart:cart_view')

    addrs = request.user.addresses.all()
    sub, tax, ship, total = _calc_totals(cart_items)
    return render(request, 'checkout.html', {
        'cart': cart, 'cart_items': cart_items,
        'shipping_addresses': addrs,
        'default_shipping': addrs.filter(is_default_shipping=True).first(),
        'default_billing': addrs.filter(is_default_billing=True).first(),
        'subtotal': sub, 'tax': tax, 'shipping': ship, 'total': total,
    })


# ─────────────────────────────────────────────────────────────
# PLACE ORDER
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def place_order(request):
    try:
        cart = get_or_create_cart(request)
        cart_items = list(
            cart.items.select_related('product','variant','lens_option')
                      .prefetch_related('lens_addons','lens_addons__addon')
        )
        if not cart_items:
            messages.error(request, 'Your cart is empty.')
            return redirect('cart:cart_view')

        pm = request.POST.get('payment_method','').strip()
        if not pm:
            messages.error(request, 'Please select a payment method.')
            return redirect('orders:checkout')

        # ── Shipping ──────────────────────────────────────────
        addr_id = request.POST.get('shipping_address_id','').strip()
        if addr_id:
            try:
                a = Address.objects.get(id=addr_id, user=request.user)
                ship = {
                    'line1': a.address_line1, 'line2': getattr(a,'address_line2','') or '',
                    'city': a.city, 'state': getattr(a,'state','') or '',
                    'country': a.country, 'postal_code': getattr(a,'postal_code','') or '',
                    'phone': getattr(a,'phone','') or '',
                    'name': getattr(a,'full_name','') or request.user.get_full_name() or request.user.email,
                }
            except Address.DoesNotExist:
                messages.error(request, 'Shipping address not found.')
                return redirect('orders:checkout')
        else:
            fn = request.POST.get('full_name','').strip()
            a1 = request.POST.get('address_line1','').strip()
            ct = request.POST.get('city','').strip()
            if not fn or not a1 or not ct:
                messages.error(request, 'Please fill in all required address fields.')
                return redirect('orders:checkout')
            ship = {
                'line1': a1, 'line2': request.POST.get('address_line2','').strip(),
                'city': ct, 'state': request.POST.get('state','').strip(),
                'country': request.POST.get('country','Qatar').strip() or 'Qatar',
                'postal_code': request.POST.get('postal_code','').strip(),
                'phone': request.POST.get('phone','').strip(), 'name': fn,
            }

        lat = request.POST.get('delivery_latitude','').strip() or None
        lng = request.POST.get('delivery_longitude','').strip() or None

        # ── Billing ───────────────────────────────────────────
        same = request.POST.get('same_as_shipping','') in ('on','true','1','yes','True')
        if same:
            bill = ship.copy()
        else:
            bid = request.POST.get('billing_address_id','').strip()
            if bid:
                try:
                    b = Address.objects.get(id=bid, user=request.user)
                    bill = {'line1':b.address_line1,'line2':getattr(b,'address_line2','') or '','city':b.city,'state':getattr(b,'state','') or '','country':b.country,'postal_code':getattr(b,'postal_code','') or ''}
                except Address.DoesNotExist:
                    bill = ship.copy()
            else:
                bill = {'line1':request.POST.get('billing_address_line1','').strip(),'line2':'','city':request.POST.get('billing_city','').strip(),'state':'','country':request.POST.get('billing_country','Qatar').strip() or 'Qatar','postal_code':''}

        sub, tax_amt, ship_amt, total = _calc_totals(cart_items)
        currency = str(getattr(cart,'currency',None) or 'QAR')

        # ── Create order ──────────────────────────────────────
        with transaction.atomic():
            order = Order.objects.create(
                order_number=_gen_order_number(), customer=request.user,
                order_type='online', status='pending', currency=currency,
                subtotal=sub, tax_amount=tax_amt, shipping_amount=ship_amt,
                discount_amount=Decimal('0.00'), total_amount=total,
                customer_email=request.user.email,
                customer_phone=ship.get('phone',''), customer_name=ship.get('name',''),
                shipping_address_line1=ship.get('line1',''), shipping_address_line2=ship.get('line2',''),
                shipping_city=ship.get('city',''), shipping_state=ship.get('state',''),
                shipping_country=ship.get('country','Qatar'), shipping_postal_code=ship.get('postal_code',''),
                delivery_latitude=_dec(lat) if lat else None,
                delivery_longitude=_dec(lng) if lng else None,
                billing_same_as_shipping=same,
                billing_address_line1=bill.get('line1',''), billing_address_line2=bill.get('line2',''),
                billing_city=bill.get('city',''), billing_state=bill.get('state',''),
                billing_country=bill.get('country','Qatar'), billing_postal_code=bill.get('postal_code',''),
                payment_method=pm, payment_status='pending',
                customer_notes=request.POST.get('customer_notes','').strip(),
            )

            for ci in cart_items:
                ip  = _dec(getattr(ci,'unit_price',0))
                lp  = _dec(getattr(ci,'lens_price',0))
                sub_item = ip * ci.quantity + (lp * ci.quantity if lp else Decimal('0'))

                vd = None
                if getattr(ci,'variant',None):
                    vd = {'color': getattr(ci.variant,'color_name',None), 'size': getattr(ci.variant,'size',None)}

                oi = OrderItem.objects.create(
                    order=order, product=ci.product,
                    variant=getattr(ci,'variant',None),
                    product_name=ci.product.name,
                    product_sku=str(getattr(ci.product,'sku','') or ''),
                    variant_details=vd, quantity=ci.quantity, unit_price=ip,
                    requires_prescription=getattr(ci,'requires_prescription',False),
                    lens_option=getattr(ci,'lens_option',None),
                    lens_option_name=str(getattr(getattr(ci,'lens_option',None),'name','') or ''),
                    lens_price=lp,
                    prescription_data=getattr(ci,'prescription_data',None),
                    contact_lens_left_power=getattr(ci,'contact_lens_left_power',None),
                    contact_lens_right_power=getattr(ci,'contact_lens_right_power',None),
                    subtotal=sub_item,
                    special_instructions=getattr(ci,'special_instructions','') or '',
                )
                try:
                    for addon in ci.lens_addons.all():
                        ao = getattr(addon,'addon',None)
                        if ao:
                            OrderItemLensAddOn.objects.create(
                                order_item=oi, addon=ao,
                                addon_name=getattr(ao,'name',''),
                                price=_dec(getattr(addon,'price',0)),
                            )
                except Exception as e:
                    logger.warning(f"Addon error: {e}")

            OrderStatusHistory.objects.create(
                order=order, to_status='pending',
                notes='Order created online', changed_by=request.user,
            )

        logger.info(f"Order {order.order_number} created | {pm} | {total}")

        # ── Route ─────────────────────────────────────────────
        if pm == 'cash_on_delivery':
            cart.items.all().delete()
            order.status       = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save(update_fields=['status','confirmed_at'])
            OrderStatusHistory.objects.create(order=order, from_status='pending', to_status='confirmed', notes='COD confirmed', changed_by=request.user)
            messages.success(request, f'✅ Order {order.order_number} placed!')
            return redirect('orders:order_confirmation', order_number=order.order_number)

        elif pm == 'sadad':
            return redirect('orders:sadad_payment', order_number=order.order_number)
        elif pm == 'stripe':
            return redirect('orders:stripe_payment', order_number=order.order_number)
        elif pm == 'razorpay':
            return redirect('orders:razorpay_payment', order_number=order.order_number)
        elif pm == 'paypal':
            return redirect('orders:paypal_payment', order_number=order.order_number)
        else:
            order.delete()
            messages.error(request, f'Unknown payment method: {pm}')
            return redirect('orders:checkout')

    except Exception as e:
        logger.error(f"place_order error: {type(e).__name__}: {e}", exc_info=True)
        messages.error(request, 'Something went wrong. Please try again.')
        return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# SADAD  — Amazon-style redirect flow
# ─────────────────────────────────────────────────────────────

@login_required
def sadad_payment(request, order_number):
    """Step 1 of 3: Build Sadad form and auto-POST to gateway."""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)

    try:
        data = SadadPaymentService.build_payment_form_data(order)
        # Store the sanitized order ID — Sadad returns THIS in ORDERID callback
        order.payment_gateway        = 'sadad'
        order.payment_transaction_id = data['safe_order_id']
        order.save(update_fields=['payment_gateway', 'payment_transaction_id'])

        return render(request, 'orders/sadad_redirect.html', {
            'order':       order,
            'action_url':  data['action_url'],
            'form_fields': data['fields'],
        })

    except SadadPaymentError as e:
        logger.error(f"Sadad config error: {e}")
        messages.error(request, str(e))
        return redirect('orders:checkout')
    except Exception as e:
        logger.error(f"sadad_payment error: {e}", exc_info=True)
        messages.error(request, f'Payment error: {e}')
        return redirect('orders:checkout')


@csrf_exempt
def sadad_payment_return(request):
    """
    Step 2 of 3: Sadad POSTs here after customer pays (or cancels).
    ORDERID = the sanitized order ID we sent (stored in payment_transaction_id).
    """
    data = request.POST.dict() if request.method == 'POST' else request.GET.dict()
    logger.info(f"Sadad return: {data}")

    # Sadad sends back our ORDER_ID as 'ORDERID'
    sadad_oid = data.get('ORDERID', '').strip()
    if not sadad_oid:
        messages.error(request, 'Invalid payment response — no ORDERID.')
        return redirect('orders:order_list')

    try:
        # Look up by what we stored in payment_transaction_id
        order = Order.objects.filter(payment_transaction_id=sadad_oid).first()
        if not order:
            logger.error(f"Sadad return: no order with payment_transaction_id={sadad_oid}")
            messages.error(request, 'Order not found.')
            return redirect('orders:order_list')

        if order.payment_status == 'completed':
            return redirect('orders:order_confirmation', order_number=order.order_number)

        verify = SadadPaymentService.verify_callback(data)

        if verify['paid']:
            _complete_sadad_order(order, verify)
            messages.success(request, '✅ Payment successful! Your order is confirmed.')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        else:
            order.payment_status           = 'failed'
            order.payment_gateway_response = data
            order.save(update_fields=['payment_status', 'payment_gateway_response'])
            if not verify['checksum_valid']:
                msg = 'Payment security check failed. Please contact support.'
            else:
                msg = f"Payment failed: {verify.get('resp_msg', 'Unknown error')} (code {verify.get('resp_code', '')})"
            messages.error(request, msg)
            return redirect('orders:checkout')

    except Exception as e:
        logger.error(f"sadad_payment_return error: {e}", exc_info=True)
        messages.error(request, 'Payment processing error.')
        return redirect('orders:order_list')


@csrf_exempt
@require_POST
def sadad_webhook(request):
    """Step 3 (optional): server-to-server webhook from Sadad."""
    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST.dict()

        sadad_oid = str(data.get('ORDERID') or data.get('id', '')).strip()
        resp_code = str(data.get('RESPCODE', '')).strip()
        txn_id    = str(data.get('transaction_number', '')).strip()

        if not sadad_oid:
            return HttpResponse('Missing ORDERID', status=400)

        order = Order.objects.filter(payment_transaction_id=sadad_oid).first()
        if not order:
            return HttpResponse('Not found', status=404)

        if resp_code == '1' and order.payment_status != 'completed':
            _complete_sadad_order(order, {
                'paid': True, 'checksum_valid': True,
                'resp_code': resp_code, 'transaction_id': txn_id,
                'amount': str(data.get('TXNAMOUNT', '')), 'raw': data,
            })
        elif resp_code not in ('', '1') and order.payment_status not in ('completed', 'failed'):
            order.payment_status = 'failed'
            order.save(update_fields=['payment_status'])

        return HttpResponse('OK', status=200)
    except Exception as e:
        logger.error(f"Sadad webhook error: {e}", exc_info=True)
        return HttpResponse('Error', status=500)


@transaction.atomic
def _complete_sadad_order(order, verify):
    order.payment_status           = 'completed'
    order.payment_gateway_response = verify.get('raw', verify)
    order.paid_at                  = timezone.now()
    order.status                   = 'confirmed'
    order.confirmed_at             = timezone.now()
    order.save()

    PaymentTransaction.objects.get_or_create(
        order=order,
        gateway_transaction_id=verify.get('transaction_id') or order.payment_transaction_id,
        defaults=dict(
            transaction_id=_gen_txn_id(), transaction_type='payment', status='completed',
            amount=order.total_amount, currency=order.currency,
            payment_gateway='sadad', payment_method='sadad',
            gateway_response=verify.get('raw', verify), completed_at=timezone.now(),
        )
    )
    cart = Cart.objects.filter(customer=order.customer).first()
    if cart:
        cart.items.all().delete()

    OrderStatusHistory.objects.create(
        order=order, from_status='pending', to_status='confirmed',
        notes=f"Paid via Sadad (txn: {verify.get('transaction_id','')})",
        changed_by=order.customer,
    )


# ─────────────────────────────────────────────────────────────
# STRIPE
# ─────────────────────────────────────────────────────────────

@login_required
def stripe_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    res = StripePaymentService.create_payment_intent(order)
    if res['success']:
        order.payment_gateway = 'stripe'
        order.payment_transaction_id = res['payment_intent_id']
        order.save()
        return render(request, 'stripe_payment.html', {
            'order': order, 'client_secret': res['client_secret'],
            'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        })
    messages.error(request, f"Stripe error: {res.get('error')}")
    return redirect('orders:checkout')


@login_required
@require_POST
def stripe_payment_confirm(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    res = StripePaymentService.confirm_payment(request.POST.get('payment_intent_id'))
    if res['success']:
        order.payment_status='completed'; order.paid_at=timezone.now()
        order.status='confirmed'; order.confirmed_at=timezone.now(); order.save()
        get_or_create_cart(request).items.all().delete()
        return JsonResponse({'success': True, 'redirect_url': reverse('orders:order_confirmation', args=[order.order_number])})
    return JsonResponse({'success': False, 'error': res.get('error')})


# ─────────────────────────────────────────────────────────────
# RAZORPAY
# ─────────────────────────────────────────────────────────────

@login_required
def razorpay_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    res = RazorpayPaymentService.create_order(order)
    if res['success']:
        order.payment_gateway='razorpay'; order.payment_transaction_id=res['razorpay_order_id']; order.save()
        return render(request, 'razorpay_payment.html', {'order':order,'razorpay_order_id':res['razorpay_order_id'],'razorpay_key_id':res['key_id'],'amount':res['amount'],'currency':res['currency']})
    messages.error(request, res.get('error','Razorpay error'))
    return redirect('orders:checkout')


@csrf_exempt
@require_POST
def razorpay_payment_verify(request):
    try:
        d = json.loads(request.body)
        res = RazorpayPaymentService.verify_payment(d['razorpay_order_id'], d['razorpay_payment_id'], d['razorpay_signature'])
        order = Order.objects.get(payment_transaction_id=d['razorpay_order_id'])
        if res['success']:
            order.payment_status='completed'; order.paid_at=timezone.now(); order.status='confirmed'; order.confirmed_at=timezone.now(); order.save()
            Cart.objects.filter(customer=order.customer).first() and Cart.objects.filter(customer=order.customer).first().items.all().delete()
            return JsonResponse({'success':True,'redirect_url':reverse('orders:order_confirmation',args=[order.order_number])})
        order.payment_status='failed'; order.save()
        return JsonResponse({'success':False,'error':res.get('error')})
    except Exception as e:
        return JsonResponse({'success':False,'error':str(e)})


# ─────────────────────────────────────────────────────────────
# PAYPAL
# ─────────────────────────────────────────────────────────────

@login_required
def paypal_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if order.payment_status == 'completed':
        return redirect('orders:order_confirmation', order_number=order.order_number)
    res = PayPalPaymentService.create_payment(
        order,
        request.build_absolute_uri(reverse('orders:paypal_execute', args=[order.order_number])),
        request.build_absolute_uri(reverse('orders:checkout'))
    )
    if res['success']:
        order.payment_gateway='paypal'; order.payment_transaction_id=res['payment_id']; order.save()
        return redirect(res['approval_url'])
    messages.error(request, res.get('error','PayPal error'))
    return redirect('orders:checkout')


@login_required
def paypal_execute(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    pid = request.GET.get('paymentId'); payer = request.GET.get('PayerID')
    if not pid or not payer:
        messages.error(request,'Payment cancelled.'); return redirect('orders:checkout')
    res = PayPalPaymentService.execute_payment(pid, payer)
    if res['success']:
        order.payment_status='completed'; order.paid_at=timezone.now(); order.status='confirmed'; order.confirmed_at=timezone.now(); order.save()
        get_or_create_cart(request).items.all().delete()
        messages.success(request,'✅ Payment successful!')
        return redirect('orders:order_confirmation', order_number=order.order_number)
    messages.error(request, res.get('error','PayPal error'))
    return redirect('orders:checkout')


# ─────────────────────────────────────────────────────────────
# ORDER VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
def order_confirmation(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'order_confirmation.html', {'order': order})


@login_required
def order_list(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    sf = request.GET.get('status')
    if sf and sf != 'all':
        orders = orders.filter(status=sf)
    return render(request, 'order_list.html', {'orders': orders, 'status_filter': sf, 'order_statuses': Order.ORDER_STATUS})


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'order_detail.html', {
        'order': order,
        'order_items': order.items.select_related('product','variant','lens_option').prefetch_related('lens_addons'),
        'status_history': order.status_history.all(),
        'payment_transactions': order.payment_transactions.all(),
    })


@login_required
def track_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    prog  = ['pending','confirmed','processing','shipped','delivered']
    idx   = prog.index(order.status) if order.status in prog else 0
    return render(request, 'track_order.html', {'order': order, 'status_history': order.status_history.all(), 'status_progression': prog, 'current_status_index': idx})


@login_required
@require_POST
def cancel_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect('orders:order_detail', order_number=order_number)
    old = order.status; order.status = 'cancelled'; order.save()
    OrderStatusHistory.objects.create(order=order, from_status=old, to_status='cancelled', notes='Cancelled by customer', changed_by=request.user)
    messages.success(request, 'Order cancelled.')
    return redirect('orders:order_detail', order_number=order_number)


@login_required
def get_order_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return JsonResponse({'order_number': order.order_number, 'status': order.status, 'status_display': order.get_status_display(), 'payment_status': order.payment_status, 'tracking_number': order.tracking_number, 'carrier': order.carrier})