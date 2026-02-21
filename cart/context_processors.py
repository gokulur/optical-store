# cart/context_processors.py
from django.db.models import Sum
from .models import Cart


def cart_processor(request):
    """
    Add cart info to template context.
    Counts total QUANTITY (sum), not distinct rows.
    """
    cart_count = 0

    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(customer=request.user).first()
            if cart:
                result = cart.items.aggregate(total=Sum('quantity'))
                cart_count = result['total'] or 0
        else:
            # Only read session_key if a session already exists — don't force-create one
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.filter(
                    session_key=session_key,
                    customer=None
                ).first()
                if cart:
                    result = cart.items.aggregate(total=Sum('quantity'))
                    cart_count = result['total'] or 0

    except Exception as e:
        print(f"Cart context processor error: {e}")

    return {
        'cart_count': cart_count,
    }