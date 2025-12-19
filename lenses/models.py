# lenses/models.py
from django.db import models
from django.core.validators import MinValueValidator


class LensCategory(models.Model):
    """Main lens categories (Single Vision, Progressive, etc.)"""
    CATEGORY_TYPES = [
        ('single_vision', 'Single-Vision Lenses'),
        ('progressive_bifocal', 'Progressive & Bifocal Lenses'),
        ('reading', 'Reading Glasses'),
        ('non_prescription', 'Without Prescription Lenses'),
    ]
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=50, choices=CATEGORY_TYPES, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'lenses_categories'
        verbose_name_plural = 'Lens Categories'
        ordering = ['display_order']


class LensOption(models.Model):
    """Individual lens options within categories"""
    category = models.ForeignKey(LensCategory, on_delete=models.CASCADE, related_name='lens_options')
    
    # Basic Info
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Technical Specs
    lens_index = models.DecimalField(max_digits=4, decimal_places=2)  # 1.50, 1.56, 1.67, etc.
    material = models.CharField(max_length=100, blank=True)
    
    # Features (stored as JSON or separate M2M)
    features = models.JSONField(default=list)  # ["Anti-reflection", "UV protection", etc.]
    
    # Power Ranges
    min_sphere_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    max_sphere_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    min_cylinder_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    max_cylinder_power = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # For reading glasses
    available_reading_powers = models.JSONField(default=list, blank=True)  # ["+1.00", "+1.25", etc.]
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lenses_options'
        ordering = ['category', 'display_order']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category', 'is_active']),
        ]


class LensAddOn(models.Model):
    """Add-ons for lens options (Blue UV, Photochromic, Tinted, etc.)"""
    ADDON_TYPES = [
        ('blue_protection', 'Blue UV Protection'),
        ('photochromic', 'Photochromic'),
        ('transition_classic', 'Transition Classic'),
        ('transition_gen_s', 'Transition Gen-S'),
        ('transition_gen_8', 'Transition Gen-8'),
        ('tinted', 'Tinted'),
        ('premium_blue', 'Premium Blue Filtration'),
        ('index_upgrade', 'Index Upgrade'),
    ]
    
    name = models.CharField(max_length=100)
    addon_type = models.CharField(max_length=50, choices=ADDON_TYPES)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'lenses_addons'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
        ]


class LensOptionAddOn(models.Model):
    """Link between lens options and available add-ons with pricing"""
    lens_option = models.ForeignKey(LensOption, on_delete=models.CASCADE, related_name='available_addons')
    addon = models.ForeignKey(LensAddOn, on_delete=models.CASCADE, related_name='lens_compatibility')
    
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'lenses_option_addons'
        unique_together = [['lens_option', 'addon']]
        ordering = ['display_order']


class SunglassLensOption(models.Model):
    """Lens options specifically for sunglasses (simplified)"""
    LENS_TYPES = [
        ('regular', 'Regular'),
        ('essilor', 'Essilor Crizal Easy Pro'),
    ]
    
    lens_type = models.CharField(max_length=50, choices=LENS_TYPES)
    name = models.CharField(max_length=200)
    
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    lens_index = models.DecimalField(max_digits=4, decimal_places=2, default=1.56)
    
    features = models.JSONField(default=list)
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'lenses_sunglass_options'
        ordering = ['display_order']