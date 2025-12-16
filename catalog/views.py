from django.shortcuts import render

# Create your views here.
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count
from .models import Product, Brand, Category, ProductVariant


@staff_member_required
def admin_dashboard(request):
    """
    Custom admin dashboard view with statistics and charts
    """
    # Get statistics
    total_products = Product.objects.filter(active=True).count()
    total_brands = Brand.objects.filter(active=True).count()
    total_categories = Category.objects.filter(active=True).count()
    
    # Get recent products
    recent_products = Product.objects.select_related(
        'brand', 'category'
    ).filter(active=True).order_by('-id')[:5]
    
    # Get products by category for chart
    products_by_category = Category.objects.annotate(
        product_count=Count('product')
    ).values('name', 'product_count').order_by('-product_count')[:6]
    
    context = {
        'total_products': total_products,
        'total_brands': total_brands,
        'total_categories': total_categories,
        'low_stock': 0,  # You can calculate this based on your inventory logic
        'recent_products': recent_products,
        'products_by_category': products_by_category,
    }
    
    return render(request, 'admin/dashboard.html', context)