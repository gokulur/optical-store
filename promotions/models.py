# promotions/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Coupon(models.Model):
    """Discount coupons"""
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    ]
    
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Conditions
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maximum_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Limitations
    usage_limit = models.PositiveIntegerField(null=True, blank=True)  # Total uses
    usage_limit_per_customer = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Applicability
    applicable_to_all = models.BooleanField(default=True)
    applicable_categories = models.ManyToManyField('catalog.Category', blank=True)
    applicable_products = models.ManyToManyField('catalog.Product', blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'coupons'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'valid_from', 'valid_until']),
        ]


class CouponUsage(models.Model):
    """Track coupon usage"""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usage_records')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='coupon_usage')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='coupon_usage')
    
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'coupon_usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['coupon', 'user']),
        ]
