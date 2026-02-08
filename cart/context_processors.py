"""
Context processor to make cart available in all templates
Add this to settings.py TEMPLATES['OPTIONS']['context_processors']
"""

from .models import Cart


def cart_processor(request):
    """Add cart info to template context"""
    cart = None
    cart_count = 0
    
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(customer=request.user).first()
        elif request.session.session_key:
            cart = Cart.objects.filter(
                session_key=request.session.session_key,
                customer=None
            ).first()
        
        if cart:
            cart_count = cart.items.count()
    except:
        pass
    
    return {
        'cart': cart,
        'cart_count': cart_count,
    }


