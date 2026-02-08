# cart/signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Cart


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """
    Merge guest cart with user cart when user logs in
    """
    try:
        # Get session key
        session_key = request.session.session_key
        if not session_key:
            return
        
        # Get guest cart
        guest_cart = Cart.objects.filter(
            session_key=session_key, 
            customer=None
        ).first()
        
        if not guest_cart or not guest_cart.items.exists():
            return
        
        # Get or create user cart
        user_cart, created = Cart.objects.get_or_create(customer=user)
        
        # Move items from guest cart to user cart
        for item in guest_cart.items.all():
            # Check if similar item exists in user cart
            existing_item = user_cart.items.filter(
                product=item.product,
                variant=item.variant,
                lens_option=item.lens_option,
                sunglass_lens_option=item.sunglass_lens_option
            ).first()
            
            if existing_item:
                # Merge quantities
                existing_item.quantity += item.quantity
                existing_item.save()
                item.delete()
            else:
                # Move item to user cart
                item.cart = user_cart
                item.save()
        
        # Delete empty guest cart
        guest_cart.delete()
        
        print(f"✅ Cart merged for user: {user.username}")
        
    except Exception as e:
        print(f"❌ Error merging cart: {str(e)}")