# promotions/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal

from .models import Coupon, CouponUsage
from cart.views import get_or_create_cart


def validate_coupon(coupon_code, user, cart_total):
    """Validate coupon and return discount info"""
    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True)
    except Coupon.DoesNotExist:
        return {'valid': False, 'error': 'Invalid coupon code'}

    now = timezone.now()

    if now < coupon.valid_from:
        return {'valid': False, 'error': 'This coupon is not yet active'}

    if now > coupon.valid_until:
        return {'valid': False, 'error': 'This coupon has expired'}

    if coupon.usage_limit and coupon.times_used >= coupon.usage_limit:
        return {'valid': False, 'error': 'This coupon has reached its usage limit'}

    if user.is_authenticated and coupon.usage_limit_per_customer:
        usage_count = CouponUsage.objects.filter(coupon=coupon, user=user).count()
        if usage_count >= coupon.usage_limit_per_customer:
            return {'valid': False, 'error': 'You have already used this coupon the maximum number of times'}

    if coupon.minimum_order_amount and cart_total < coupon.minimum_order_amount:
        return {
            'valid': False,
            'error': f'Minimum order amount of QAR {coupon.minimum_order_amount} required'
        }

    # Calculate discount
    discount_amount = Decimal('0.00')

    if coupon.discount_type == 'percentage':
        discount_amount = (cart_total * coupon.discount_value) / 100
        if coupon.maximum_discount_amount:
            discount_amount = min(discount_amount, coupon.maximum_discount_amount)

    elif coupon.discount_type == 'fixed_amount':
        discount_amount = min(coupon.discount_value, cart_total)

    elif coupon.discount_type == 'free_shipping':
        discount_amount = Decimal('0.00')  # Free shipping handled at checkout

    return {
        'valid': True,
        'coupon': coupon,
        'discount_amount': discount_amount,
        'discount_type': coupon.discount_type,
    }


def _get_cart_subtotal(request):
    """Helper: compute cart subtotal including lens prices and addons."""
    cart = get_or_create_cart(request)
    subtotal = Decimal('0.00')
    for item in cart.items.all():
        item_total = item.unit_price * item.quantity
        if item.lens_price:
            item_total += item.lens_price * item.quantity
        for addon in item.lens_addons.all():
            item_total += addon.price * item.quantity
        subtotal += item_total
    return subtotal


@require_POST
def apply_coupon(request):
    """Apply coupon to cart session."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Please log in to use coupons'})

    coupon_code = request.POST.get('coupon_code', '').strip()
    if not coupon_code:
        return JsonResponse({'success': False, 'error': 'Please enter a coupon code'})

    subtotal = _get_cart_subtotal(request)
    result   = validate_coupon(coupon_code, request.user, subtotal)

    if not result['valid']:
        return JsonResponse({'success': False, 'error': result['error']})

    # Store in session — all values as strings so JSON serialisation is safe
    request.session['applied_coupon'] = {
        'code':            result['coupon'].code.upper(),
        'discount_amount': str(result['discount_amount'].quantize(Decimal('0.01'))),
        'discount_type':   result['discount_type'],
    }
    request.session.modified = True

    return JsonResponse({
        'success':         True,
        'discount_amount': str(result['discount_amount']),
        'message':         f'Coupon "{coupon_code.upper()}" applied successfully!',
    })


@require_POST
def remove_coupon(request):
    """Remove applied coupon from session."""
    request.session.pop('applied_coupon', None)
    request.session.modified = True
    return JsonResponse({'success': True, 'message': 'Coupon removed'})


@login_required
def my_coupons(request):
    """View available and used coupons for the logged-in user."""
    now = timezone.now()

    available_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now,
    )

    # Annotate each coupon with can_use flag
    for coupon in available_coupons:
        coupon.can_use = True
        if coupon.usage_limit and coupon.times_used >= coupon.usage_limit:
            coupon.can_use = False
        if coupon.can_use and coupon.usage_limit_per_customer:
            usage_count = CouponUsage.objects.filter(
                coupon=coupon, user=request.user
            ).count()
            if usage_count >= coupon.usage_limit_per_customer:
                coupon.can_use = False

    # Coupon usage history for this user
    used_coupons = CouponUsage.objects.filter(
        user=request.user
    ).select_related('coupon', 'order').order_by('-created_at')

    # Total saved across all coupon usages
    total_saved = sum(
        u.discount_amount for u in used_coupons if u.discount_amount
    )

    context = {
        'available_coupons': available_coupons,
        'used_coupons':      used_coupons,
        'total_saved':       total_saved,
    }

    return render(request, 'my_coupons.html', context)


def active_promotions(request):
    """View all active promotions (public)."""
    now = timezone.now()

    promotions = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now,
    ).order_by('-discount_value')

    return render(request, 'promotions.html', {'promotions': promotions})