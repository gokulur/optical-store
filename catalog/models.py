from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
 

class Category(models.Model):
    """Main product categories"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # For filtering
    product_type = models.CharField(max_length=50, choices=[
        ('sunglasses', 'Sunglasses'),
        ('eyeglasses', 'Eyeglasses'),
        ('contact_lenses', 'Contact Lenses'),
        ('accessories', 'Accessories'),
        ('reading_glasses', 'Reading Glasses'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'catalog_categories'
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['product_type', 'is_active']),
        ]


class Brand(models.Model):
    """Optical brands"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    logo = models.ImageField(upload_to='brands/')
    description = models.TextField(blank=True)
    
    # Brand availability across categories
    available_for_sunglasses = models.BooleanField(default=False)
    available_for_eyeglasses = models.BooleanField(default=False)
    available_for_kids = models.BooleanField(default=False)
    available_for_contact_lenses = models.BooleanField(default=False)
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'catalog_brands'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]


class Product(models.Model):
    """Base product model for all optical products"""
    
    PRODUCT_TYPES = [
        ('sunglasses', 'Sunglasses'),
        ('eyeglasses', 'Eyeglasses'),
        ('contact_lenses', 'Contact Lenses'),
        ('accessories', 'Accessories'),
        ('reading_glasses', 'Reading Glasses'),
    ]
    
    GENDER_CHOICES = [
        ('unisex', 'Unisex'),
        ('men', 'Men'),
        ('women', 'Women'),
        ('kids', 'Kids'),
    ]
    
    # Basic Info
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True, db_index=True)
    
    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPES, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    
    # Descriptions
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Categorization
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='unisex')
    age_group = models.CharField(max_length=20, choices=[
        ('adult', 'Adult'),
        ('kids', 'Kids'),
    ], default='adult')
    
    # Inventory
    track_inventory = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    allow_backorder = models.BooleanField(default=False)
    
    # SEO & Marketing
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_on_sale = models.BooleanField(default=False)
    
    # Analytics
    views_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'catalog_products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['slug']),
            models.Index(fields=['product_type', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
            models.Index(fields=['-created_at']),
        ]


class ProductVariant(models.Model):
    """Product color/size variants"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    # Variant identifiers
    variant_sku = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Variant attributes
    color_name = models.CharField(max_length=100, blank=True)
    color_code = models.CharField(max_length=20, blank=True)  # Hex color
    size = models.CharField(max_length=50, blank=True)  # Frame size
    
    # Frame specifications (for glasses)
    lens_width = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bridge_width = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temple_length = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Pricing (if variant has different price)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Inventory
    stock_quantity = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'catalog_product_variants'
        ordering = ['is_default', 'color_name']
        indexes = [
            models.Index(fields=['variant_sku']),
            models.Index(fields=['product', 'is_active']),
        ]
        unique_together = [['product', 'color_name', 'size']]


class ProductImage(models.Model):
    """Product images"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name='images')
    
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'catalog_product_images'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['product', 'display_order']),
        ]


class ProductSpecification(models.Model):
    """Technical specifications for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    
    spec_key = models.CharField(max_length=100)  # e.g., "Frame Material", "Lens Material"
    spec_value = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'catalog_product_specifications'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['product']),
        ]


class ContactLensProduct(models.Model):
    """Extended details for contact lenses"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='contact_lens_details')
    
    LENS_TYPES = [
        ('clear', 'Clear'),
        ('color', 'Color'),
    ]
    
    REPLACEMENT_SCHEDULES = [
        ('daily', 'Daily'),
        ('monthly', 'Monthly'),
        ('3_months', 'Up to 3 Months'),
    ]
    
    lens_type = models.CharField(max_length=20, choices=LENS_TYPES)
    replacement_schedule = models.CharField(max_length=20, choices=REPLACEMENT_SCHEDULES)
    package_size = models.IntegerField(default=2)  # Number of lenses per pack
    
    # Technical specs
    diameter = models.DecimalField(max_digits=4, decimal_places=2)  # in mm
    base_curve = models.DecimalField(max_digits=3, decimal_places=1)
    water_content = models.DecimalField(max_digits=4, decimal_places=1)  # percentage
    
    # Power availability
    power_available = models.BooleanField(default=True)
    min_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    max_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Color lens specific
    color_name = models.CharField(max_length=100, blank=True)
    color_image = models.ImageField(upload_to='contact_lenses/colors/', null=True, blank=True)
    
    intended_use = models.CharField(max_length=100, default='Vision Correction')
    
    class Meta:
        db_table = 'catalog_contact_lens_products'
        indexes = [
            models.Index(fields=['lens_type', 'replacement_schedule']),
        ]


class ContactLensPowerOption(models.Model):
    """Available power options for contact lenses"""
    contact_lens = models.ForeignKey(ContactLensProduct, on_delete=models.CASCADE, related_name='power_options')
    
    power_value = models.DecimalField(max_digits=4, decimal_places=2)  # e.g., -1.00, -2.50
    is_available = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'catalog_contact_lens_power_options'
        unique_together = [['contact_lens', 'power_value']]
        ordering = ['power_value']
        indexes = [
            models.Index(fields=['contact_lens', 'is_available']),
        ]


class ProductTag(models.Model):
    """Tags for products (e.g., "Bestseller", "New Arrival")"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    
    class Meta:
        db_table = 'catalog_product_tags'


class ProductTagRelation(models.Model):
    """M2M relationship between products and tags"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_tags')
    tag = models.ForeignKey(ProductTag, on_delete=models.CASCADE, related_name='tagged_products')
    
    class Meta:
        db_table = 'catalog_product_tag_relations'
        unique_together = [['product', 'tag']]