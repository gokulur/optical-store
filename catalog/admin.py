from django.contrib import admin
from unfold.admin import ModelAdmin  # Import Unfold's ModelAdmin
from .models import (
    Brand, Category, Product, ProductVariant,
    ContactLensPower, LensRule, LensPowerAvailability,
    LensOption, LensAddon
)


@admin.register(Brand)
class BrandAdmin(ModelAdmin):  # Changed from admin.ModelAdmin to ModelAdmin
    list_display = ("name", "active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    list_filter = ("active",)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):  # Changed
    list_display = ("name", "parent", "active")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("active",)
    search_fields = ("name",)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class LensRuleInline(admin.TabularInline):
    model = LensRule
    extra = 0


@admin.register(Product)
class ProductAdmin(ModelAdmin):  # Changed
    list_display = ("name", "brand", "category", "product_type", "active")
    list_filter = ("brand", "category", "product_type", "active")
    search_fields = ("name", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline, LensRuleInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):  # Changed
    list_display = ("product", "color_name", "is_power_allowed", "active")
    list_filter = ("is_power_allowed", "active")
    search_fields = ("product__name", "color_name")


@admin.register(ContactLensPower)
class ContactLensPowerAdmin(ModelAdmin):  # Changed
    list_display = ("value", "is_plano")
    list_filter = ("is_plano",)


@admin.register(LensPowerAvailability)
class LensPowerAvailabilityAdmin(ModelAdmin):  # Changed
    list_display = ("variant", "power", "is_available", "stock")
    list_filter = ("is_available",)
    search_fields = ("variant__product__name",)


class LensAddonInline(admin.TabularInline):
    model = LensAddon
    extra = 1


@admin.register(LensOption)
class LensOptionAdmin(ModelAdmin):  # Changed
    list_display = ("name", "provider", "base_price")
    inlines = [LensAddonInline]