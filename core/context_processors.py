
from catalog.models import Brand
from cart.views import get_or_create_cart


def global_context(request):
    """
    Injects common context variables into every template:
      - nav_brands       : active brands for nav dropdowns
      - cart_count       : number of items in cart
      - wishlist_count   : number of wishlist items (authenticated users)
    """
    # Navigation brands (top 10 by display_order)
    nav_brands = Brand.objects.filter(is_active=True).order_by('display_order')[:10]

    # Cart count
    cart_count = 0
    cart = None
    try:
        cart = get_or_create_cart(request)
        cart_count = cart.items.count()
    except Exception:
        pass

    # Wishlist count (only for authenticated users)
    wishlist_count = 0
    if request.user.is_authenticated:
        try:
            wishlist_count = request.user.wishlist.products.count()
        except Exception:
            pass

    return {
        'nav_brands':      nav_brands,
        'cart':            cart,
        'cart_count':      cart_count,
        'wishlist_count':  wishlist_count,
    }