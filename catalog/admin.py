from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import (
    Brand, Category, Product, ProductVariant,
    ContactLensPower, LensRule, LensPowerAvailability,
    LensOption, LensAddon
)


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    list_filter = ("active",)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
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
class ProductAdmin(ModelAdmin):
    list_display = [
        "product_image_display",
        "name",
        "brand_display",
        "category_display",
        "product_type",
        "active",
    ]
    list_filter = ["brand", "category", "product_type", "active"]
    search_fields = ["name", "brand__name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline, LensRuleInline]
    
    @display(description="Image", header=True)
    def product_image_display(self, obj):
        if hasattr(obj, 'image') and obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px;" />',
                obj.image.url
            )
        return format_html(
            '<div style="width: 50px; height: 50px; background: #f3f4f6; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 10px; color: #9ca3af;">No Image</div>'
        )
    
    @display(description="Brand", ordering="brand__name")
    def brand_display(self, obj):
        return format_html(
            '<span style="background: #e0e7ff; color: #4338ca; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            obj.brand.name
        )
    
    @display(description="Category", ordering="category__name")
    def category_display(self, obj):
        return format_html(
            '<span style="background: #dbeafe; color: #1e40af; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            obj.category.name
        )


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = ("product", "color_name", "is_power_allowed", "active")
    list_filter = ("is_power_allowed", "active")
    search_fields = ("product__name", "color_name")


@admin.register(ContactLensPower)
class ContactLensPowerAdmin(ModelAdmin):
    list_display = ("value", "is_plano")
    list_filter = ("is_plano",)


@admin.register(LensPowerAvailability)
class LensPowerAvailabilityAdmin(ModelAdmin):
    list_display = ("variant", "power", "is_available", "stock")
    list_filter = ("is_available",)
    search_fields = ("variant__product__name",)


class LensAddonInline(admin.TabularInline):
    model = LensAddon
    extra = 1


@admin.register(LensOption)
class LensOptionAdmin(ModelAdmin):
    list_display = ("name", "provider", "base_price")
    inlines = [LensAddonInline]


# Dashboard callback function for custom widgets
def dashboard_callback(request, context):
    """
    Callback to add custom widgets and charts to the dashboard
    """
    # Get counts for metrics
    total_products = Product.objects.count()
    total_brands = Brand.objects.filter(active=True).count()
    total_categories = Category.objects.count()
    
    # Update context with real data
    context.update({
        "total_products": total_products,
        "total_brands": total_brands,
        "total_categories": total_categories,
        "recent_products": Product.objects.select_related('brand', 'category').order_by('-id')[:5],
    })
    
    return context