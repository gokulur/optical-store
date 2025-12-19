# cart/models.py
from django.db import models
from django.conf import settings
from catalog.models import Product, ProductVariant
from lenses.models import LensOption, LensAddOn, SunglassLensOption


class Cart(models.Model):
    """Shopping cart"""
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=255, db_index=True, null=True, blank=True)  # For guest users
    
    # Currency
    currency = models.CharField(max_length=3, default='QAR')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_carts'
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['session_key']),
        ]


class CartItem(models.Model):
    """Individual cart items with lens customization"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    
    # Product Info
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    
    quantity = models.PositiveIntegerField(default=1)
    
    # Base price at time of adding
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Lens Configuration (for eyeglasses/sunglasses)
    requires_prescription = models.BooleanField(default=False)
    
    # For eyeglasses
    lens_option = models.ForeignKey(LensOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    
    # For sunglasses
    sunglass_lens_option = models.ForeignKey(SunglassLensOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    
    # Lens pricing
    lens_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Prescription data (stored as JSON for flexibility)
    prescription_data = models.JSONField(null=True, blank=True)
    
    # For contact lenses with power
    contact_lens_left_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    contact_lens_right_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Notes
    special_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cart']),
        ]


class CartItemLensAddOn(models.Model):
    """Add-ons selected for cart item lenses"""
    cart_item = models.ForeignKey(CartItem, on_delete=models.CASCADE, related_name='lens_addons')
    addon = models.ForeignKey(LensAddOn, on_delete=models.CASCADE)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'cart_item_lens_addons'
        unique_together = [['cart_item', 'addon']]