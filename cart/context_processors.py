# cart/context_processors.py
from django.db.models import Sum
from .models import Cart


def cart_processor(request):
    """Add cart info to template context — counts total quantity not distinct rows"""
    cart = None
    cart_count = 0

    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(customer=request.user).first()
        else:
            # Make sure session exists before reading session_key
            if not request.session.session_key:
                request.session.create()
            cart = Cart.objects.filter(
                session_key=request.session.session_key,
                customer=None
            ).first()

        if cart:
            # Sum quantities — so 1 item with qty=2 shows 2, not 1
            result = cart.items.aggregate(total=Sum('quantity'))
            cart_count = result['total'] or 0

    except Exception as e:
        print(f"Cart context processor error: {e}")

    return {
        'cart': cart,
        'cart_count': cart_count,
    }