# orders/views.py - COMPLETE WITH PAYMENT INTEGRATION
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
from django.conf import settings
from .models import Order, OrderItem, OrderItemLensAddOn, OrderStatusHistory, PaymentTransaction
from cart.models import Cart, CartItem
from users.models import Address
from cart.views import get_or_create_cart
from .payment_services import (
    StripePaymentService,
    RazorpayPaymentService,
    PayPalPaymentService,
    PaymentGatewayFactory,
    PaymentGatewayError
)


def generate_order_number():
    """Generate unique order number"""
    timestamp = timezone.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"


def generate_transaction_id():
    """Generate unique transaction ID"""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"TXN-{timestamp}-{random_str}"


@login_required
def checkout(request):
    """Checkout page"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option'
    ).prefetch_related('lens_addons')
    
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart:cart_view')
    
    # Get user addresses
    shipping_addresses = request.user.addresses.all()
    default_shipping = shipping_addresses.filter(is_default_shipping=True).first()
    default_billing = shipping_addresses.filter(is_default_billing=True).first()
    
    # Calculate totals
    subtotal = Decimal('0.00')
    for item in cart_items:
        item_total = item.unit_price * item.quantity
        if item.lens_price:
            item_total += item.lens_price * item.quantity
        for addon in item.lens_addons.all():
            item_total += addon.price * item.quantity
        subtotal += item_total
    
    # Calculate tax and shipping
    tax_rate = Decimal('0.00')
    tax = subtotal * tax_rate
    
    shipping = Decimal('0.00')
    if subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')
    
    total = subtotal + tax + shipping
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'shipping_addresses': shipping_addresses,
        'default_shipping': default_shipping,
        'default_billing': default_billing,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        # Payment gateway keys (for frontend)
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }
    
    return render(request, 'checkout.html', context)


@login_required
@require_POST
@transaction.atomic
def place_order(request):
    """Place order from cart - handles payment initiation"""
    try:
        cart = get_or_create_cart(request)
        cart_items = cart.items.all()
        
        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('cart:cart_view')
        
        # Get form data
        payment_method = request.POST.get('payment_method')
        customer_notes = request.POST.get('customer_notes', '')
        
        # Get or create address from form
        if request.POST.get('shipping_address_id'):
            shipping_address = get_object_or_404(Address, id=request.POST.get('shipping_address_id'), user=request.user)
            
            shipping_info = {
                'line1': shipping_address.address_line1,
                'line2': shipping_address.address_line2,
                'city': shipping_address.city,
                'state': shipping_address.state,
                'country': shipping_address.country,
                'postal_code': shipping_address.postal_code,
                'phone': shipping_address.phone,
                'name': shipping_address.full_name,
            }
        else:
            # Manual address entry
            shipping_info = {
                'line1': request.POST.get('address_line1', ''),
                'line2': request.POST.get('address_line2', ''),
                'city': request.POST.get('city', ''),
                'state': request.POST.get('state', ''),
                'country': request.POST.get('country', 'India'),
                'postal_code': request.POST.get('postal_code', ''),
                'phone': request.POST.get('phone', ''),
                'name': request.POST.get('full_name', request.user.get_full_name()),
            }
        
        # Get location coordinates
        delivery_latitude = request.POST.get('delivery_latitude')
        delivery_longitude = request.POST.get('delivery_longitude')
        
        # Billing address
        billing_same = request.POST.get('same_as_shipping') == 'on'
        if billing_same:
            billing_info = shipping_info.copy()
        else:
            billing_address = get_object_or_404(Address, id=request.POST.get('billing_address_id'), user=request.user)
            billing_info = {
                'line1': billing_address.address_line1,
                'line2': billing_address.address_line2,
                'city': billing_address.city,
                'state': billing_address.state,
                'country': billing_address.country,
                'postal_code': billing_address.postal_code,
            }
        
        # Calculate totals
        subtotal = Decimal('0.00')
        for item in cart_items:
            item_total = item.unit_price * item.quantity
            if item.lens_price:
                item_total += item.lens_price * item.quantity
            for addon in item.lens_addons.all():
                item_total += addon.price * item.quantity
            subtotal += item_total
        
        tax = Decimal('0.00')
        shipping_amount = Decimal('0.00')
        if subtotal < Decimal('200.00'):
            shipping_amount = Decimal('20.00')
        
        total = subtotal + tax + shipping_amount
        
        # Create order
        order = Order.objects.create(
            order_number=generate_order_number(),
            customer=request.user,
            order_type='online',
            status='pending',
            currency=cart.currency,
            subtotal=subtotal,
            tax_amount=tax,
            shipping_amount=shipping_amount,
            discount_amount=Decimal('0.00'),
            total_amount=total,
            customer_email=request.user.email,
            customer_phone=shipping_info['phone'],
            customer_name=shipping_info['name'],
            shipping_address_line1=shipping_info['line1'],
            shipping_address_line2=shipping_info['line2'],
            shipping_city=shipping_info['city'],
            shipping_state=shipping_info['state'],
            shipping_country=shipping_info['country'],
            shipping_postal_code=shipping_info['postal_code'],
            delivery_latitude=Decimal(delivery_latitude) if delivery_latitude else None,
            delivery_longitude=Decimal(delivery_longitude) if delivery_longitude else None,
            billing_same_as_shipping=billing_same,
            billing_address_line1=billing_info['line1'],
            billing_address_line2=billing_info['line2'],
            billing_city=billing_info['city'],
            billing_state=billing_info['state'],
            billing_country=billing_info['country'],
            billing_postal_code=billing_info['postal_code'],
            payment_method=payment_method,
            payment_status='pending',
            customer_notes=customer_notes
        )
        
        # Create order items
        for cart_item in cart_items:
            item_subtotal = cart_item.unit_price * cart_item.quantity
            if cart_item.lens_price:
                item_subtotal += cart_item.lens_price * cart_item.quantity
            
            order_item = OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku,
                variant_details={
                    'color': cart_item.variant.color_name if cart_item.variant else None,
                    'size': cart_item.variant.size if cart_item.variant else None,
                },
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                requires_prescription=cart_item.requires_prescription,
                lens_option=cart_item.lens_option,
                lens_option_name=cart_item.lens_option.name if cart_item.lens_option else '',
                lens_price=cart_item.lens_price,
                prescription_data=cart_item.prescription_data,
                contact_lens_left_power=cart_item.contact_lens_left_power,
                contact_lens_right_power=cart_item.contact_lens_right_power,
                subtotal=item_subtotal,
                special_instructions=cart_item.special_instructions
            )
            
            # Create lens add-ons
            for addon_item in cart_item.lens_addons.all():
                OrderItemLensAddOn.objects.create(
                    order_item=order_item,
                    addon=addon_item.addon,
                    addon_name=addon_item.addon.name,
                    price=addon_item.price
                )
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            to_status='pending',
            notes='Order created',
            changed_by=request.user
        )
        
        # Route to appropriate payment handler
        if payment_method == 'cash_on_delivery':
            # Clear cart
            cart.items.all().delete()
            messages.success(request, 'Order placed successfully! Pay when you receive your order.')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        
        elif payment_method == 'stripe':
            return redirect('orders:stripe_payment', order_number=order.order_number)
        
        elif payment_method == 'razorpay':
            return redirect('orders:razorpay_payment', order_number=order.order_number)
        
        elif payment_method == 'paypal':
            return redirect('orders:paypal_payment', order_number=order.order_number)
        
        else:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('orders:checkout')
        
    except Exception as e:
        messages.error(request, f'Error placing order: {str(e)}')
        return redirect('orders:checkout')


# ============================================
# STRIPE PAYMENT VIEWS
# ============================================

@login_required
def stripe_payment(request, order_number):
    """Stripe payment page"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)
    
    try:
        # Create Stripe payment intent
        result = StripePaymentService.create_payment_intent(order)
        
        if result['success']:
            # Store payment gateway info
            order.payment_gateway = 'stripe'
            order.payment_transaction_id = result['payment_intent_id']
            order.save()
            
            context = {
                'order': order,
                'client_secret': result['client_secret'],
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            }
            return render(request, 'stripe_payment.html', context)
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    
    except Exception as e:
        messages.error(request, f'Error initializing payment: {str(e)}')
        return redirect('orders:checkout')


@login_required
@require_POST
def stripe_payment_confirm(request, order_number):
    """Confirm Stripe payment"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    try:
        payment_intent_id = request.POST.get('payment_intent_id')
        
        result = StripePaymentService.confirm_payment(payment_intent_id)
        
        if result['success']:
            # Update order
            order.payment_status = 'completed'
            order.payment_gateway_response = result
            order.paid_at = timezone.now()
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Create payment transaction record
            PaymentTransaction.objects.create(
                order=order,
                transaction_id=generate_transaction_id(),
                gateway_transaction_id=payment_intent_id,
                transaction_type='payment',
                status='completed',
                amount=order.total_amount,
                currency=order.currency,
                payment_gateway='stripe',
                payment_method='card',
                gateway_response=result,
                completed_at=timezone.now()
            )
            
            # Clear cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                from_status='pending',
                to_status='confirmed',
                notes='Payment confirmed via Stripe',
                changed_by=request.user
            )
            
            return JsonResponse({'success': True, 'redirect_url': reverse('orders:order_confirmation', args=[order.order_number])})
        else:
            return JsonResponse({'success': False, 'error': result.get('error')})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================
# RAZORPAY PAYMENT VIEWS
# ============================================

@login_required
def razorpay_payment(request, order_number):
    """Razorpay payment page"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)
    
    try:
        # Create Razorpay order
        result = RazorpayPaymentService.create_order(order)
        
        if result['success']:
            # Store payment gateway info
            order.payment_gateway = 'razorpay'
            order.payment_transaction_id = result['razorpay_order_id']
            order.save()
            
            context = {
                'order': order,
                'razorpay_order_id': result['razorpay_order_id'],
                'razorpay_key_id': result['key_id'],
                'amount': result['amount'],
                'currency': result['currency'],
            }
            return render(request, 'orders/razorpay_payment.html', context)
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    
    except Exception as e:
        messages.error(request, f'Error initializing payment: {str(e)}')
        return redirect('orders:checkout')


@csrf_exempt
@require_POST
def razorpay_payment_verify(request):
    """Verify Razorpay payment webhook"""
    try:
        data = json.loads(request.body)
        
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        
        # Find order
        order = Order.objects.get(payment_transaction_id=razorpay_order_id)
        
        # Verify signature
        result = RazorpayPaymentService.verify_payment(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        )
        
        if result['success']:
            # Update order
            order.payment_status = 'completed'
            order.payment_gateway_response = result
            order.paid_at = timezone.now()
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Create payment transaction
            PaymentTransaction.objects.create(
                order=order,
                transaction_id=generate_transaction_id(),
                gateway_transaction_id=razorpay_payment_id,
                transaction_type='payment',
                status='completed',
                amount=order.total_amount,
                currency=order.currency,
                payment_gateway='razorpay',
                payment_method=result.get('method', 'card'),
                card_last4=result.get('card_last4', ''),
                card_brand=result.get('card_network', ''),
                gateway_response=result,
                completed_at=timezone.now()
            )
            
            # Clear cart
            cart = Cart.objects.filter(customer=order.customer).first()
            if cart:
                cart.items.all().delete()
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                from_status='pending',
                to_status='confirmed',
                notes='Payment confirmed via Razorpay',
                changed_by=order.customer
            )
            
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('orders:order_confirmation', args=[order.order_number])
            })
        else:
            order.payment_status = 'failed'
            order.save()
            return JsonResponse({'success': False, 'error': result.get('error')})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================
# PAYPAL PAYMENT VIEWS
# ============================================

@login_required
def paypal_payment(request, order_number):
    """PayPal payment page"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:order_confirmation', order_number=order.order_number)
    
    try:
        # Create PayPal payment
        return_url = request.build_absolute_uri(reverse('orders:paypal_execute', args=[order.order_number]))
        cancel_url = request.build_absolute_uri(reverse('orders:checkout'))
        
        result = PayPalPaymentService.create_payment(order, return_url, cancel_url)
        
        if result['success']:
            # Store payment gateway info
            order.payment_gateway = 'paypal'
            order.payment_transaction_id = result['payment_id']
            order.save()
            
            # Redirect to PayPal approval URL
            return redirect(result['approval_url'])
        else:
            messages.error(request, f"Payment error: {result.get('error')}")
            return redirect('orders:checkout')
    
    except Exception as e:
        messages.error(request, f'Error initializing payment: {str(e)}')
        return redirect('orders:checkout')


@login_required
def paypal_execute(request, order_number):
    """Execute PayPal payment after approval"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    try:
        payment_id = request.GET.get('paymentId')
        payer_id = request.GET.get('PayerID')
        
        if not payment_id or not payer_id:
            messages.error(request, 'Payment cancelled or invalid.')
            return redirect('orders:checkout')
        
        result = PayPalPaymentService.execute_payment(payment_id, payer_id)
        
        if result['success']:
            # Update order
            order.payment_status = 'completed'
            order.payment_gateway_response = result
            order.paid_at = timezone.now()
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Create payment transaction
            PaymentTransaction.objects.create(
                order=order,
                transaction_id=generate_transaction_id(),
                gateway_transaction_id=payment_id,
                transaction_type='payment',
                status='completed',
                amount=order.total_amount,
                currency=order.currency,
                payment_gateway='paypal',
                payment_method='paypal',
                gateway_response=result,
                completed_at=timezone.now()
            )
            
            # Clear cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                from_status='pending',
                to_status='confirmed',
                notes='Payment confirmed via PayPal',
                changed_by=request.user
            )
            
            messages.success(request, 'Payment successful!')
            return redirect('orders:order_confirmation', order_number=order.order_number)
        else:
            messages.error(request, f"Payment failed: {result.get('error')}")
            return redirect('orders:checkout')
    
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('orders:checkout')


# ============================================
# ORDER CONFIRMATION & MANAGEMENT
# ============================================

@login_required
def order_confirmation(request, order_number):
    """Order confirmation page"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    context = {
        'order': order,
    }
    
    return render(request, 'orders/order_confirmation.html', context)


@login_required
def order_list(request):
    """List user's orders"""
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
        'order_statuses': Order.ORDER_STATUS,
    }
    
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail(request, order_number):
    """Order detail page"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    order_items = order.items.select_related(
        'product', 'variant', 'lens_option'
    ).prefetch_related('lens_addons')
    
    # Get status history
    status_history = order.status_history.all()
    
    # Get payment transactions
    payment_transactions = order.payment_transactions.all()
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_history': status_history,
        'payment_transactions': payment_transactions,
    }
    
    return render(request, 'orders/order_detail.html', context)


@login_required
def track_order(request, order_number):
    """Track order status"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    # Get status history
    status_history = order.status_history.all()
    
    # Define status progression
    status_progression = [
        'pending',
        'confirmed',
        'processing',
        'shipped',
        'delivered'
    ]
    
    current_status_index = status_progression.index(order.status) if order.status in status_progression else 0
    
    context = {
        'order': order,
        'status_history': status_history,
        'status_progression': status_progression,
        'current_status_index': current_status_index,
    }
    
    return render(request, 'orders/track_order.html', context)


@login_required
@require_POST
def cancel_order(request, order_number):
    """Cancel an order"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    # Can only cancel pending/confirmed orders
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect('orders:order_detail', order_number=order_number)
    
    # Update status
    old_status = order.status
    order.status = 'cancelled'
    order.save()
    
    # Create status history
    OrderStatusHistory.objects.create(
        order=order,
        from_status=old_status,
        to_status='cancelled',
        notes='Cancelled by customer',
        changed_by=request.user
    )
    
    messages.success(request, 'Order cancelled successfully.')
    return redirect('orders:order_detail', order_number=order_number)


# AJAX endpoint
@login_required
def get_order_status(request, order_number):
    """Get order status (AJAX)"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    return JsonResponse({
        'order_number': order.order_number,
        'status': order.status,
        'status_display': order.get_status_display(),
        'payment_status': order.payment_status,
        'tracking_number': order.tracking_number,
        'carrier': order.carrier,
    })