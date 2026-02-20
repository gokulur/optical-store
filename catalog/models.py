from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
 
 

class Category(models.Model):
    PRODUCT_TYPES = [
        ('sunglasses', 'Sunglasses'),
        ('eyeglasses', 'Eyeglasses'),
        ('contact_lenses', 'Contact Lenses'),
        ('accessories', 'Accessories'),
        ('reading_glasses', 'Reading Glasses'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
  
    has_prescription = models.BooleanField(default=False)
    has_lens_selection = models.BooleanField(default=False)
    has_power = models.BooleanField(default=False)
    has_color_variants = models.BooleanField(default=False)
    has_size_variants = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'catalog_categories'
        ordering = ['display_order', 'name']



class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='brands/')
    description = models.TextField(blank=True)

    available_for_sunglasses = models.BooleanField(default=False)
    available_for_eyeglasses = models.BooleanField(default=False)
    available_for_kids = models.BooleanField(default=False)
    available_for_contact_lenses = models.BooleanField(default=False)

    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalog_brands'



class Product(models.Model):
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

    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPES)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, null=True, blank=True)

    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)

    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='unisex')
    age_group = models.CharField(
    max_length=20,
    choices=[('adult','Adult'),('kids','Kids')],
    default='adult')

    track_inventory = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalog_products'

    @property
    def is_in_stock(self):
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0



class ProductVariant(models.Model):
    VARIANT_TYPES = [
        ('frame', 'Frame'),
        ('color', 'Color'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
 

    variant_sku = models.CharField(max_length=100, unique=True)

    color_name = models.CharField(max_length=100, blank=True)
    color_code = models.CharField(max_length=20, blank=True)
    size = models.CharField(max_length=50, blank=True)

    lens_width = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bridge_width = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temple_length = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'catalog_product_variants'



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
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='contact_lens')

    lens_type = models.CharField(max_length=20, choices=[('clear','Clear'),('color','Color')])
    replacement_schedule = models.CharField(
        max_length=20,
        choices=[('daily','Daily'),('monthly','Monthly'),('3_months','Up to 3 Months')]
    )

    package_size = models.IntegerField(default=2)
    diameter = models.DecimalField(max_digits=4, decimal_places=2)
    base_curve = models.DecimalField(max_digits=3, decimal_places=1)
    water_content = models.DecimalField(max_digits=4, decimal_places=1)

    intended_use = models.CharField(max_length=100, default='Vision / Cosmetic')

    class Meta:
        db_table = 'catalog_contact_lens_products'


class ContactLensColor(models.Model):
    contact_lens = models.ForeignKey(
        ContactLensProduct,
        on_delete=models.CASCADE,
        related_name='colors'
    )

    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='contact_lenses/colors/')
    is_active = models.BooleanField(default=True)

    power_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'catalog_contact_lens_colors'

class ContactLensPowerOption(models.Model):
    color = models.ForeignKey(
        ContactLensColor,
        on_delete=models.CASCADE,
        related_name='power_options',
        null=True,       
        blank=True      
    )


    power_value = models.DecimalField(max_digits=4, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = 'catalog_contact_lens_power_options'
        unique_together = ['color', 'power_value']



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


class LensBrand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'name']



class LensType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    requires_power = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)



class LensOption(models.Model):
    lens_brand = models.ForeignKey(LensBrand, on_delete=models.CASCADE)
    lens_type = models.ForeignKey(LensType, on_delete=models.CASCADE)

    index = models.CharField(max_length=10)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)

    min_power = models.DecimalField(max_digits=4, decimal_places=2)
    max_power = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        db_table = 'catalog_lens_options'
