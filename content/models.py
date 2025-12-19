# content/models.py
from django.db import models


class Banner(models.Model):
    """Homepage and category banners"""
    BANNER_TYPES = [
        ('homepage', 'Homepage'),
        ('category', 'Category'),
        ('promotional', 'Promotional'),
    ]
    
    PLACEMENT_CHOICES = [
        ('main_slider', 'Main Slider'),
        ('secondary', 'Secondary Banner'),
        ('sidebar', 'Sidebar'),
    ]
    
    title = models.CharField(max_length=200)
    banner_type = models.CharField(max_length=50, choices=BANNER_TYPES)
    placement = models.CharField(max_length=50, choices=PLACEMENT_CHOICES)
    
    image_desktop = models.ImageField(upload_to='banners/desktop/')
    image_mobile = models.ImageField(upload_to='banners/mobile/', null=True, blank=True)
    image_tablet = models.ImageField(upload_to='banners/tablet/', null=True, blank=True)
    
    # Link
    link_url = models.URLField(blank=True)
    link_type = models.CharField(max_length=50, choices=[
        ('product', 'Product'),
        ('category', 'Category'),
        ('brand', 'Brand'),
        ('page', 'Page'),
        ('external', 'External'),
    ], blank=True)
    
    # For direct product integration
    linked_product_id = models.IntegerField(null=True, blank=True)
    
    # Scheduling
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Auto-slide settings
    auto_slide = models.BooleanField(default=True)
    slide_duration = models.PositiveIntegerField(default=5)  # seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'content_banners'
        ordering = ['placement', 'display_order']
        indexes = [
            models.Index(fields=['banner_type', 'is_active']),
            models.Index(fields=['placement', 'display_order']),
        ]


class Page(models.Model):
    """Static pages (About Us, Contact, etc.)"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, db_index=True)
    
    content = models.TextField()
    
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'content_pages'
        ordering = ['title']


class StoreLocation(models.Model):
    """Physical store locations"""
    name = models.CharField(max_length=200)
    
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True)
    
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    
    # Map coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    google_maps_url = models.URLField(blank=True)
    
    # Operating hours (stored as JSON)
    operating_hours = models.JSONField(default=dict)  # {"monday": "9:00-18:00", ...}
    
    # Features
    offers_eye_test = models.BooleanField(default=False)
    is_flagship = models.BooleanField(default=False)
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'content_store_locations'
        ordering = ['display_order', 'name']


class EyeTestBooking(models.Model):
    """Eye test appointment bookings"""
    BOOKING_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='eye_test_bookings')
    location = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name='eye_test_bookings')
    
    booking_date = models.DateField()
    booking_time = models.TimeField()
    
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField()
    
    status = models.CharField(max_length=50, choices=BOOKING_STATUS, default='pending')
    
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'content_eye_test_bookings'
        ordering = ['-booking_date', '-booking_time']
        indexes = [
            models.Index(fields=['customer', '-booking_date']),
            models.Index(fields=['location', 'booking_date']),
            models.Index(fields=['status']),
        ]