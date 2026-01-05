"""
Signal handlers for cart operations
Add this to cart/apps.py in the ready() method
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .views import merge_guest_cart_on_login


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """
    Merge guest cart with user cart when user logs in
    """
    if request.session.session_key:
        merge_guest_cart_on_login(user, request.session.session_key)