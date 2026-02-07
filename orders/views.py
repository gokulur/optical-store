from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import random
import string

from .models import Order, OrderItem, OrderItemLensAddOn, OrderStatusHistory
from cart.models import Cart, CartItem
from users.models import Address
from cart.views import get_or_create_cart


def generate_order_number():
    """Generate unique order number"""
    timestamp = timezone.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"


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
    tax_rate = Decimal('0.00')  # Adjust as needed
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
    }
    
    return render(request, 'checkout.html', context)


@login_required
@require_POST
@transaction.atomic
def place_order(request):
    """Place order from cart"""
    try:
        cart = get_or_create_cart(request)
        cart_items = cart.items.all()
        
        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('cart:cart_view')
        
        # Get form data
        shipping_address_id = request.POST.get('shipping_address_id')
        billing_address_id = request.POST.get('billing_address_id')
        payment_method = request.POST.get('payment_method')
        customer_notes = request.POST.get('customer_notes', '')
        
        # Get addresses
        shipping_address = get_object_or_404(Address, id=shipping_address_id, user=request.user)
        
        if billing_address_id and billing_address_id != shipping_address_id:
            billing_address = get_object_or_404(Address, id=billing_address_id, user=request.user)
            billing_same = False
        else:
            billing_address = shipping_address
            billing_same = True
        
        # Calculate totals
        subtotal = Decimal('0.00')
        for item in cart_items:
            item_total = item.unit_price * item.quantity
            if item.lens_price:
                item_total += item.lens_price * item.quantity
            for addon in item.lens_addons.all():
                item_total += addon.price * item.quantity
            subtotal += item_total
        
        tax_rate = Decimal('0.00')
        tax = subtotal * tax_rate
        
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
            customer_phone=request.user.phone or shipping_address.phone,
            customer_name=request.user.get_full_name() or shipping_address.full_name,
            shipping_address_line1=shipping_address.address_line1,
            shipping_address_line2=shipping_address.address_line2,
            shipping_city=shipping_address.city,
            shipping_state=shipping_address.state,
            shipping_country=shipping_address.country,
            shipping_postal_code=shipping_address.postal_code,
            billing_same_as_shipping=billing_same,
            billing_address_line1=billing_address.address_line1,
            billing_address_line2=billing_address.address_line2,
            billing_city=billing_address.city,
            billing_state=billing_address.state,
            billing_country=billing_address.country,
            billing_postal_code=billing_address.postal_code,
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
                item_subtotal += addon_item.price * cart_item.quantity
            
            # Update order item subtotal
            order_item.subtotal = item_subtotal
            order_item.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            to_status='pending',
            notes='Order created',
            changed_by=request.user
        )
        
        # Clear cart
        cart.items.all().delete()
        
        # Process payment (placeholder)
        if payment_method == 'cash_on_delivery':
            order.payment_status = 'pending'
            order.save()
        # Add other payment methods here
        
        messages.success(request, 'Order placed successfully!')
        return redirect('orders:order_confirmation', order_number=order.order_number)
        
    except Exception as e:
        messages.error(request, f'Error placing order: {str(e)}')
        return redirect('orders:checkout')


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
    
    return render(request, 'order_list.html', context)


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
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_history': status_history,
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
    
    # Get status timeline
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
    if order.status not in ['pending', 'confirmed']:
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


@login_required
def reorder(request, order_number):
    """Reorder - add items from previous order to cart"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )
    
    cart = get_or_create_cart(request)
    
    # Add order items to cart
    for order_item in order.items.all():
        # Check if product still active
        if not order_item.product.is_active:
            continue
        
        cart_item = CartItem.objects.create(
            cart=cart,
            product=order_item.product,
            variant=order_item.variant,
            quantity=order_item.quantity,
            unit_price=order_item.product.base_price,  # Use current price
            requires_prescription=order_item.requires_prescription,
            lens_option=order_item.lens_option,
            lens_price=order_item.lens_price,
            prescription_data=order_item.prescription_data,
            special_instructions=order_item.special_instructions
        )
    
    messages.success(request, 'Items added to cart from previous order!')
    return redirect('cart:cart_view')


# AJAX endpoints
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
        'tracking_number': order.tracking_number,
        'carrier': order.carrier,
        'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
        'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None,
    })