# orders/models.py
from django.db import models
from django.conf import settings
from catalog.models import Product, ProductVariant
from lenses.models import LensOption, LensAddOn
import uuid


class Order(models.Model):
    """Main order model"""
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    ORDER_TYPES = [
        ('online', 'Online'),
        ('in_store', 'In-Store'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    # Order Identifiers
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default='online')
    
    # Status
    status = models.CharField(max_length=50, choices=ORDER_STATUS, default='pending', db_index=True)
    
    # Pricing
    currency = models.CharField(max_length=3, default='QAR')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Customer Info (snapshot at order time)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=200)
    
    # Shipping Address
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_country = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    
    # Location coordinates
    delivery_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Billing Address
    billing_same_as_shipping = models.BooleanField(default=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    
    # Payment
    payment_method = models.CharField(max_length=50, blank=True)
    payment_status = models.CharField(max_length=50, choices=PAYMENT_STATUS, default='pending')
    payment_gateway = models.CharField(max_length=50, blank=True)  # stripe, razorpay, paypal, etc.
    payment_transaction_id = models.CharField(max_length=255, blank=True)
    payment_gateway_response = models.JSONField(null=True, blank=True)  # Store full response
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Refund tracking
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_transaction_id = models.CharField(max_length=255, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    tracking_number = models.CharField(max_length=255, blank=True)
    carrier = models.CharField(max_length=100, blank=True)

    # Notes
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['payment_status']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.email}"
    
    @property
    def is_paid(self):
        return self.payment_status == 'completed'
    
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'confirmed'] and self.payment_status != 'completed'
    
    @property
    def can_be_refunded(self):
        return self.payment_status == 'completed' and self.status not in ['refunded', 'cancelled']


class OrderItem(models.Model):
    """Individual items within an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')

    # Product snapshot
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)

    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)
    variant_details = models.JSONField(null=True, blank=True)

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Lens Configuration
    requires_prescription = models.BooleanField(default=False)
    lens_option = models.ForeignKey(LensOption, on_delete=models.PROTECT, null=True, blank=True)
    lens_option_name = models.CharField(max_length=200, blank=True)
    lens_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Prescription data snapshot
    prescription_data = models.JSONField(null=True, blank=True)

    # Contact lens powers
    contact_lens_left_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    contact_lens_right_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    # Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    # Job Tracking
    job_number = models.CharField(max_length=100, blank=True, db_index=True)
    job_status = models.CharField(max_length=50, blank=True)

    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_items'
        ordering = ['id']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['job_number']),
        ]
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class OrderItemLensAddOn(models.Model):
    """Lens add-ons associated with an order item"""
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='lens_addons')
    addon = models.ForeignKey(LensAddOn, on_delete=models.PROTECT)
    addon_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'order_item_lens_addons'
    
    def __str__(self):
        return f"{self.addon_name} - QAR {self.price}"


class OrderStatusHistory(models.Model):
    """Track order status changes"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=50, blank=True)
    to_status = models.CharField(max_length=50)
    notes = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} → {self.to_status}"


class PaymentTransaction(models.Model):
    """Track all payment transactions"""
    TRANSACTION_TYPE = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('partial_refund', 'Partial Refund'),
    ]
    
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_transactions')
    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True)
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='QAR')
    
    payment_gateway = models.CharField(max_length=50)  # stripe, razorpay, paypal
    payment_method = models.CharField(max_length=50)  # card, upi, netbanking, etc.
    
    # Gateway response
    gateway_response = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Card/Payment details (masked)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['gateway_transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - {self.transaction_id} - QAR {self.amount}"