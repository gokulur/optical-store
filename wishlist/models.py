# wishlist/models.py

from django.db import models
from django.conf import settings
from catalog.models import Product


class Wishlist(models.Model):
    """One wishlist per user — created automatically on first toggle."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist of {self.user.email}"

    @property
    def count(self):
        return self.products.count()


class WishlistItem(models.Model):
    """Individual product in a wishlist."""
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlisted_by',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.product.name} in {self.wishlist}"