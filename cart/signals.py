# cart/signals.py
"""
Signal handlers for cart functionality.
Merges guest cart into user cart on login.
"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .views import merge_guest_cart_on_login


@receiver(user_logged_in)
def merge_cart_on_login(sender, user, request, **kwargs):
    """
    Automatically merge guest cart with user cart when user logs in.
    """
    if request.session.session_key:
        merge_guest_cart_on_login(user, request.session.session_key)