from django.db import models
from decimal import Decimal

PRODUCT_TYPES = [
    ("sunglass", "Sunglass"),
    ("eyeglass", "Eyeglass"),
    ("contact_lens", "Contact Lens"),
]

class Brand(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    logo = models.ImageField(upload_to="brands/", null=True, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children"
    )
    type = models.CharField(max_length=30, choices=PRODUCT_TYPES, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["slug", "parent"], name="unique_category_slug_parent")
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=270, unique=True)
    description = models.TextField(blank=True)

    product_type = models.CharField(max_length=30, choices=PRODUCT_TYPES)
    has_power = models.BooleanField(default=False)

    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    attributes = models.JSONField(default=dict, blank=True)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand} - {self.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")

    sku = models.CharField(max_length=120, null=True, blank=True)
    color_name = models.CharField(max_length=120)
    color_code = models.CharField(max_length=20, null=True, blank=True)

    images = models.JSONField(default=list, blank=True)

    is_power_allowed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "color_name"], name="unique_product_color")
        ]
        indexes = [
            models.Index(fields=["product", "color_name"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.color_name}"


class ContactLensPower(models.Model):
    value = models.DecimalField(max_digits=5, decimal_places=2, unique=True)
    is_plano = models.BooleanField(default=False)

    def __str__(self):
        return str(self.value)


class LensRule(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="lens_rules")

    allow_plano = models.BooleanField(default=True)
    allow_power = models.BooleanField(default=False)

    power_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    power_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    note = models.TextField(blank=True)

    def __str__(self):
        return f"Lens rules for {self.product.name}"


class LensPowerAvailability(models.Model):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="power_availabilities"
    )
    power = models.ForeignKey(ContactLensPower, on_delete=models.CASCADE)

    is_available = models.BooleanField(default=False)
    is_special_order = models.BooleanField(default=False)
    stock = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "power"], name="unique_variant_power")
        ]
        indexes = [
            models.Index(fields=["variant", "power"]),
        ]

    def __str__(self):
        return f"{self.variant} - {self.power}"


class LensOption(models.Model):
    name = models.CharField(max_length=200)
    provider = models.CharField(max_length=150, blank=True)
    index = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    features = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class LensAddon(models.Model):
    lens_option = models.ForeignKey(
        LensOption,
        on_delete=models.CASCADE,
        related_name="addons"
    )
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"{self.lens_option.name} - {self.name}"
