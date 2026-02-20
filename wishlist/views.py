from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods

from .models import Wishlist, WishlistItem
from catalog.models import Product


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_or_create_wishlist(user):
    """Return the user's wishlist, creating it if it doesn't exist."""
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


def get_wishlist_count(wishlist):
    """
    Safely get wishlist item count.
    Handles .count as @property, method, or missing attribute.
    """
    try:
        val = wishlist.count
        return val() if callable(val) else int(val)
    except Exception:
        return wishlist.items.count()


def ajax_or_json(request):
    """Returns True if the request expects a JSON response."""
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
    )


# ─────────────────────────────────────────────
# WISHLIST PAGE
# ─────────────────────────────────────────────

@login_required
def wishlist_view(request):
    """Full wishlist page — GET only."""
    wishlist = get_or_create_wishlist(request.user)
    items = wishlist.items.select_related(
        'product', 'product__brand', 'product__category'
    ).prefetch_related('product__images', 'product__variants')

    wishlist_ids = set(wishlist.items.values_list('product_id', flat=True))

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
# TOGGLE (add / remove) — POST only
# ─────────────────────────────────────────────

@require_POST
def toggle_wishlist(request, product_id):
    """
    Toggle a product in/out of the wishlist.
    - 401 JSON  → not authenticated (AJAX)
    - 200 JSON  → success
    - 500 JSON  → server error (AJAX), exception re-raised otherwise
    """
    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({
                'error': 'login_required',
                'message': 'Please log in to save items to your wishlist.',
            }, status=401)
        return redirect(f'/accounts/login/?next=/wishlist/')

    try:
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

        count = get_wishlist_count(wishlist)

        if is_ajax:
            return JsonResponse({
                'added':          added,
                'wishlist_count': count,
                'message':        message,
                'product_id':     product_id,
            })

        messages.success(request, message)
        return redirect(request.META.get('HTTP_REFERER', '/'))

    except Exception as exc:
        import traceback
        traceback.print_exc()
        if is_ajax:
            return JsonResponse({'error': 'server_error', 'message': str(exc)}, status=500)
        raise


# ─────────────────────────────────────────────
# LEGACY /wishlist/toggle/  (POST body contains product_id)
# ─────────────────────────────────────────────

@require_POST
def toggle_wishlist_post(request):
    """POST body: { product_id: <id> } — backward-compat."""
    import json

    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({
                'error': 'login_required',
                'message': 'Please log in to save items to your wishlist.',
            }, status=401)
        return redirect('/accounts/login/?next=/wishlist/')

    try:
        data       = json.loads(request.body)
        product_id = data.get('product_id')
    except Exception:
        product_id = request.POST.get('product_id')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    return toggle_wishlist(request, product_id)


# ─────────────────────────────────────────────
# REMOVE single item — GET or POST accepted
# ─────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def remove_from_wishlist(request, product_id):
    """Hard remove. Accepts both GET (wishlist.html JS uses GET) and POST."""
    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'error': 'login_required'}, status=401)
        return redirect('/accounts/login/')

    try:
        product  = get_object_or_404(Product, id=product_id)
        wishlist = get_or_create_wishlist(request.user)
        WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()
        count = get_wishlist_count(wishlist)

        if is_ajax:
            return JsonResponse({
                'success':        True,
                'wishlist_count': count,
                'product_id':     product_id,
            })

        messages.success(request, f'"{product.name}" removed from your wishlist.')
        return redirect('wishlist:wishlist')

    except Exception as exc:
        import traceback
        traceback.print_exc()
        if is_ajax:
            return JsonResponse({'error': str(exc)}, status=500)
        raise


# ─────────────────────────────────────────────
# CLEAR entire wishlist — POST only
# ─────────────────────────────────────────────

@require_POST
def clear_wishlist(request):
    """Remove every item from the wishlist in one shot."""
    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'error': 'login_required'}, status=401)
        return redirect('/accounts/login/')

    try:
        wishlist = get_or_create_wishlist(request.user)
        deleted, _ = wishlist.items.all().delete()

        if is_ajax:
            return JsonResponse({'success': True, 'deleted': deleted, 'wishlist_count': 0})

        messages.success(request, 'Your wishlist has been cleared.')
        return redirect('wishlist:wishlist')

    except Exception as exc:
        import traceback
        traceback.print_exc()
        if is_ajax:
            return JsonResponse({'error': str(exc)}, status=500)
        raise


# ─────────────────────────────────────────────
# MOVE TO CART — POST only
# ─────────────────────────────────────────────

@require_POST
def move_to_cart(request, product_id):
    """Add the product to the cart then remove it from the wishlist."""
    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'error': 'login_required'}, status=401)
        return redirect('/accounts/login/')

    try:
        from cart.views import get_or_create_cart as get_cart
        from cart.models import CartItem

        product  = get_object_or_404(Product, id=product_id, is_active=True)
        wishlist = get_or_create_wishlist(request.user)
        cart     = get_cart(request)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 1, 'unit_price': product.base_price},
        )
        if not created:
            cart_item.quantity += 1
            cart_item.save()

        WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

        if is_ajax:
            return JsonResponse({
                'success':        True,
                'cart_count':     cart.items.count(),
                'wishlist_count': get_wishlist_count(wishlist),
                'message':        f'"{product.name}" moved to cart!',
            })

        messages.success(request, f'"{product.name}" moved to cart!')
        return redirect('wishlist:wishlist')

    except Exception as exc:
        import traceback
        traceback.print_exc()
        if is_ajax:
            return JsonResponse({'error': str(exc)}, status=500)
        raise


# ─────────────────────────────────────────────
# MOVE ALL TO CART — POST only
# ─────────────────────────────────────────────

@require_POST
def move_all_to_cart(request):
    """Move every wishlist item to the cart at once."""
    is_ajax = ajax_or_json(request)

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'error': 'login_required'}, status=401)
        return redirect('/accounts/login/')

    try:
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

        if is_ajax:
            return JsonResponse({
                'success':        True,
                'moved':          moved,
                'cart_count':     cart.items.count(),
                'wishlist_count': 0,
            })

        messages.success(request, f'{moved} item(s) moved to your cart.')
        return redirect('wishlist:wishlist')

    except Exception as exc:
        import traceback
        traceback.print_exc()
        if is_ajax:
            return JsonResponse({'error': str(exc)}, status=500)
        raise


# ─────────────────────────────────────────────
# WISHLIST COUNT — GET only
# ─────────────────────────────────────────────

def wishlist_count(request):
    """Quick endpoint to refresh the badge count in the header."""
    if not request.user.is_authenticated:
        return JsonResponse({'wishlist_count': 0})
    try:
        wishlist = get_or_create_wishlist(request.user)
        return JsonResponse({'wishlist_count': get_wishlist_count(wishlist)})
    except Exception:
        return JsonResponse({'wishlist_count': 0})