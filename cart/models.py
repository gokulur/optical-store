# cart/models.py
from django.db import models
from django.conf import settings
from catalog.models import Product, ProductVariant
from lenses.models import LensOption, LensAddOn, SunglassLensOption


class Cart(models.Model):
    """Shopping cart"""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='carts'
    )
    session_key = models.CharField(
        max_length=255, 
        db_index=True, 
        null=True, 
        blank=True
    )  # For guest users
    
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
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
    
    def __str__(self):
        if self.customer:
            return f"Cart for {self.customer.email}"
        return f"Guest Cart ({self.session_key[:8]}...)"
    
    @property
    def item_count(self):
        """Total number of items in cart"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Total quantity of all items"""
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """Individual cart items with lens customization"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    
    # Product Info
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    quantity = models.PositiveIntegerField(default=1)
    
    # Base price at time of adding
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Lens Configuration (for eyeglasses/sunglasses)
    requires_prescription = models.BooleanField(default=False)
    
    # For eyeglasses
    lens_option = models.ForeignKey(
        LensOption, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cart_items'
    )
    
    # For sunglasses
    sunglass_lens_option = models.ForeignKey(
        SunglassLensOption, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cart_items'
    )
    
    # Lens pricing
    lens_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Prescription data (stored as JSON for flexibility)
    prescription_data = models.JSONField(null=True, blank=True)
    
    # For contact lenses with power
    contact_lens_left_power = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    contact_lens_right_power = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Notes
    special_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cart']),
            models.Index(fields=['product']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    @property
    def item_subtotal(self):
        """Subtotal for this item (product price only)"""
        return self.unit_price * self.quantity
    
    @property
    def lens_subtotal(self):
        """Subtotal for lens options"""
        total = self.lens_price * self.quantity
        
        # Add lens add-ons
        for addon in self.lens_addons.all():
            total += addon.price * self.quantity
        
        return total
    
    @property
    def total_price(self):
        """Total price including product and lens options"""
        return self.item_subtotal + self.lens_subtotal


class CartItemLensAddOn(models.Model):
    """Add-ons selected for cart item lenses"""
    cart_item = models.ForeignKey(
        CartItem, 
        on_delete=models.CASCADE, 
        related_name='lens_addons'
    )
    addon = models.ForeignKey(LensAddOn, on_delete=models.CASCADE)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'cart_item_lens_addons'
        unique_together = [['cart_item', 'addon']]
        verbose_name = 'Cart Item Lens Add-on'
        verbose_name_plural = 'Cart Item Lens Add-ons'
    
    def __str__(self):
        return f"{self.addon.name} for {self.cart_item.product.name}"