from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Brand, Category, Product, ProductVariant,
    ContactLensPower, LensRule, LensPowerAvailability,
    LensOption, LensAddon
)


# -------------------------
# Brand
# -------------------------
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    list_filter = ("active",)


# -------------------------
# Category
# -------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "active")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("active",)
    search_fields = ("name",)


# -------------------------
# Inlines
# -------------------------
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class LensRuleInline(admin.TabularInline):
    model = LensRule
    extra = 0


# -------------------------
# Product
# -------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_image",
        "name",
        "brand",
        "category",
        "product_type",
        "active",
    )
    list_filter = ("brand", "category", "product_type", "active")
    search_fields = ("name", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductVariantInline, LensRuleInline)

    def product_image(self, obj):
        """
        Safe image display
        """
        if hasattr(obj, "image") and obj.image:
            return format_html(
                '<img src="{}" width="45" height="45" style="object-fit:cover;border-radius:6px;" />',
                obj.image.url
            )
        return "—"

    product_image.short_description = "Image"


# -------------------------
# Product Variant
# -------------------------
@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "color_name", "is_power_allowed", "active")
    list_filter = ("is_power_allowed", "active")
    search_fields = ("product__name", "color_name")


# -------------------------
# Contact Lens Power
# -------------------------
@admin.register(ContactLensPower)
class ContactLensPowerAdmin(admin.ModelAdmin):
    list_display = ("value", "is_plano")
    list_filter = ("is_plano",)


# -------------------------
# Lens Power Availability
# -------------------------
@admin.register(LensPowerAvailability)
class LensPowerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("variant", "power", "is_available", "stock")
    list_filter = ("is_available",)
    search_fields = ("variant__product__name",)


# -------------------------
# Lens Options
# -------------------------
class LensAddonInline(admin.TabularInline):
    model = LensAddon
    extra = 1


@admin.register(LensOption)
class LensOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "base_price")
    inlines = (LensAddonInline,)
