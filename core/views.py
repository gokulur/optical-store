from django.shortcuts import render
from catalog.models import Product

# Create your views here.

from django.shortcuts import render
from catalog.models import Product

def format_products_for_template(products_queryset):
    """Helper to format data for the frontend design"""
    products_data = []
    
    for product in products_queryset:
        # 1. Get Images
        primary_image = product.images.filter(is_primary=True).first()
        if not primary_image:
            primary_image = product.images.first()
        
        secondary_image = product.images.exclude(id=primary_image.id if primary_image else None).first()
        
        # 2. Get Variants (for color swatches)
        variants = product.variants.filter(is_active=True)[:4]
        
        # 3. Calculate Discount
        discount_percentage = None
        if product.compare_at_price and product.compare_at_price > product.base_price:
            discount_percentage = int(
                ((product.compare_at_price - product.base_price) / product.compare_at_price) * 100
            )

        products_data.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'sku': product.sku,
            'base_price': product.base_price,
            'compare_at_price': product.compare_at_price,
            'discount_percentage': discount_percentage,
            'primary_image': primary_image,
            'secondary_image': secondary_image,
            'variants': variants,
        })
    return products_data

def home(request):
    # Tab 1: Latest
    latest_qs = Product.objects.filter(is_active=True).order_by('-created_at')[:8]
    latest_products = format_products_for_template(latest_qs)

    # Tab 2: Top Rated (Simulated using 'is_featured')
    top_qs = Product.objects.filter(is_active=True, is_featured=True).order_by('-base_price')[:8]
    top_rated_products = format_products_for_template(top_qs)

    # Tab 3: Best Sellers (Simulated using ID ordering)
    best_qs = Product.objects.filter(is_active=True).order_by('id')[:8]
    best_seller_products = format_products_for_template(best_qs)

    context = {
        'latest_products': latest_products,
        'top_rated_products': top_rated_products,
        'best_seller_products': best_seller_products,
    }
    
    return render(request, 'base.html', context)


def product_detail(request, slug):
    """Product detail view"""
    product = Product.objects.filter(slug=slug, is_active=True).select_related(
        'category',
        'brand'
    ).prefetch_related(
        'images',
        'variants',
        'variants__images'
    ).first()
    
    if not product:
        return render(request, '404.html', status=404)
    
    context = {
        'product': product,
    }
    
    return render(request, 'product_detail.html', context)

def about(request):
    return render(request,'about.html')

def contact(request):
    return render(request,'contact.html')