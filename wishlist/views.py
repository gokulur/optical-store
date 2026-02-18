from django.shortcuts import render

# Create your views here.
# wishlist/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Wishlist, WishlistItem
from catalog.models import Product


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_or_create_wishlist(user):
    """Return the user's wishlist, creating it if it doesn't exist."""
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


# ─────────────────────────────────────────────
# WISHLIST PAGE
# ─────────────────────────────────────────────

@login_required
def wishlist_view(request):
    """Full wishlist page."""
    wishlist = get_or_create_wishlist(request.user)
    items = wishlist.items.select_related(
        'product', 'product__brand', 'product__category'
    ).prefetch_related('product__images', 'product__variants')

    # IDs already in wishlist (used to highlight hearts in suggested section)
    wishlist_ids = set(wishlist.items.values_list('product_id', flat=True))

    # Suggested products: active products NOT already in wishlist
    suggested_products = Product.objects.filter(
        is_active=True, is_featured=True
    ).exclude(
        id__in=wishlist_ids
    ).select_related('brand').prefetch_related('images')[:8]

    context = {
        'wishlist':           wishlist,
        'items':              items,
        'item_count':         items.count(),
        'wishlist_ids':       wishlist_ids,
        'suggested_products': suggested_products,
    }
    return render(request, 'wishlist.html', context)


# ─────────────────────────────────────────────
# TOGGLE (add / remove) — used by every heart button
# ─────────────────────────────────────────────

@login_required
@require_POST
def toggle_wishlist(request, product_id):
    """
    Add the product if it isn't in the wishlist; remove it if it is.
    Returns JSON for AJAX calls and redirects for plain-HTML forms.
    """
    product  = get_object_or_404(Product, id=product_id, is_active=True)
    wishlist = get_or_create_wishlist(request.user)

    item = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()

    if item:
        item.delete()
        added   = False
        message = f'"{product.name}" removed from your wishlist.'
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        added   = True
        message = f'"{product.name}" added to your wishlist!'

    wishlist_count = wishlist.count

    # AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'added':          added,
            'wishlist_count': wishlist_count,
            'message':        message,
            'product_id':     product_id,
        })

    # Plain-form fallback
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'wishlist:wishlist'))


# ─────────────────────────────────────────────
# LEGACY /wishlist/toggle/  (no product_id in URL)
# ─────────────────────────────────────────────

@login_required
@require_POST
def toggle_wishlist_post(request):
    """
    POST body: { product_id: <id> }
    Kept for backward-compat with the base.html AJAX call pattern.
    """
    import json
    try:
        data       = json.loads(request.body)
        product_id = data.get('product_id')
    except Exception:
        product_id = request.POST.get('product_id')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    return toggle_wishlist(request, product_id)


# ─────────────────────────────────────────────
# REMOVE single item (GET or POST, no toggle)
# ─────────────────────────────────────────────

@login_required
def remove_from_wishlist(request, product_id):
    """Hard remove — always removes regardless of current state."""
    product  = get_object_or_404(Product, id=product_id)
    wishlist = get_or_create_wishlist(request.user)
    WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success':        True,
            'wishlist_count': wishlist.count,
            'product_id':     product_id,
        })

    messages.success(request, f'"{product.name}" removed from your wishlist.')
    return redirect('wishlist:wishlist')


# ─────────────────────────────────────────────
# CLEAR entire wishlist
# ─────────────────────────────────────────────

@login_required
@require_POST
def clear_wishlist(request):
    """Remove every item from the wishlist in one shot."""
    wishlist = get_or_create_wishlist(request.user)
    deleted, _ = wishlist.items.all().delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'deleted': deleted, 'wishlist_count': 0})

    messages.success(request, 'Your wishlist has been cleared.')
    return redirect('wishlist:wishlist')


# ─────────────────────────────────────────────
# MOVE TO CART
# ─────────────────────────────────────────────

@login_required
@require_POST
def move_to_cart(request, product_id):
    """
    Add the product to the cart then remove it from the wishlist.
    Relies on the cart app's get_or_create_cart helper.
    """
    from cart.views import get_or_create_cart as get_cart
    from cart.models import CartItem

    product  = get_object_or_404(Product, id=product_id, is_active=True)
    wishlist = get_or_create_wishlist(request.user)
    cart     = get_cart(request)

    # Add to cart (quantity 1, or increment if already there)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1, 'unit_price': product.base_price},
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    # Remove from wishlist
    WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

    cart_count     = cart.items.count()
    wishlist_count = wishlist.count

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success':        True,
            'cart_count':     cart_count,
            'wishlist_count': wishlist_count,
            'message':        f'"{product.name}" moved to cart!',
        })

    messages.success(request, f'"{product.name}" moved to cart!')
    return redirect('wishlist:wishlist')


# ─────────────────────────────────────────────
# MOVE ALL TO CART
# ─────────────────────────────────────────────

@login_required
@require_POST
def move_all_to_cart(request):
    """Move every wishlist item to the cart at once."""
    from cart.views import get_or_create_cart as get_cart
    from cart.models import CartItem

    wishlist = get_or_create_wishlist(request.user)
    cart     = get_cart(request)
    moved    = 0

    for wish_item in wishlist.items.select_related('product'):
        product = wish_item.product
        if not product.is_active:
            continue
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 1, 'unit_price': product.base_price},
        )
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        moved += 1

    wishlist.items.all().delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success':        True,
            'moved':          moved,
            'cart_count':     cart.items.count(),
            'wishlist_count': 0,
        })

    messages.success(request, f'{moved} item(s) moved to your cart.')
    return redirect('wishlist:wishlist')


# ─────────────────────────────────────────────
# WISHLIST COUNT (AJAX helper)
# ─────────────────────────────────────────────

@login_required
def wishlist_count(request):
    """Quick endpoint to refresh the badge count in the header."""
    wishlist = get_or_create_wishlist(request.user)
    return JsonResponse({'wishlist_count': wishlist.count})