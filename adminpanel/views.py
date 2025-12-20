# adminpanel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from catalog import models
from catalog.models import (
    Category, Brand, Product, ProductVariant, ProductImage,
    ProductSpecification, ContactLensProduct, ContactLensPowerOption,
    ProductTag, ProductTagRelation
)
from lenses.models import (
    LensCategory, LensOption, LensAddOn, LensOptionAddOn, SunglassLensOption
)
from orders.models import Order, OrderItem, OrderStatusHistory
from users.models import User, CustomerProfile, Address
from prescriptions.models import Prescription
from cart.models import Cart, CartItem
from content.models import Banner, Page, StoreLocation, EyeTestBooking
from reviews.models import Review, ReviewImage
from django.db.models import F

# from notifications.models import Notification, StockAlert
# from promotions.models import Coupon, CouponUsage
# from analytics.models import ProductView, CartAbandonment
# from settings.models import SiteSettings, Currency, TaxRate


# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and user.user_type in ['admin', 'staff']


# ==================== DASHBOARD ====================

# @login_required
# @user_passes_test(is_admin)
def dashboard(request):
    """Admin dashboard with statistics"""
    
    # Date ranges
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    
    # Orders statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    today_orders = Order.objects.filter(created_at__date=today).count()
    month_orders = Order.objects.filter(created_at__date__gte=last_30_days).count()
    
    # Revenue statistics
    total_revenue = Order.objects.filter(payment_status='paid').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    month_revenue = Order.objects.filter(
        payment_status='paid',
        created_at__date__gte=last_30_days
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Products statistics
    total_products = Product.objects.filter(is_active=True).count()
    low_stock_products = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=F('low_stock_threshold')
    ).count()
    out_of_stock = Product.objects.filter(
        track_inventory=True,
        stock_quantity=0
    ).count()
    
    # Customers
    total_customers = User.objects.filter(user_type='customer').count()
    new_customers = User.objects.filter(
        user_type='customer',
        created_at__date__gte=last_30_days
    ).count()
    
    # Recent orders
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
    
    # Top selling products
    top_products = Product.objects.filter(is_active=True).order_by('-sales_count')[:5]
    
    # Pending reviews
    pending_reviews = Review.objects.filter(is_approved=False).count()
    
    # Eye test bookings pending
    pending_bookings = EyeTestBooking.objects.filter(status='pending').count()
    
    # Low stock alerts
    low_stock_items = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=F('low_stock_threshold'),
        stock_quantity__gt=0
    ).select_related('brand', 'category')[:10]
    
    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'today_orders': today_orders,
        'month_orders': month_orders,
        'total_revenue': total_revenue,
        'month_revenue': month_revenue,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock': out_of_stock,
        'total_customers': total_customers,
        'new_customers': new_customers,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'pending_reviews': pending_reviews,
        'pending_bookings': pending_bookings,
        'low_stock_items': low_stock_items,
    }
    
    return render(request, "admin-dashboard.html", context)
 

# ==================== CATEGORIES ====================

# @login_required
# @user_passes_test(is_admin)
def category_list(request):
    """List all categories"""
    search = request.GET.get('search', '')
    product_type = request.GET.get('product_type', '')
    
    categories = Category.objects.all().order_by('display_order', 'name')
    
    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    if product_type:
        categories = categories.filter(product_type=product_type)
    
    paginator = Paginator(categories, 25)
    page = request.GET.get('page', 1)
    categories = paginator.get_page(page)
    
    context = {
        'categories': categories,
        'search': search,
        'product_type': product_type,
    }
    return render(request, 'category_list.html', context)

 
def add_category_page(request):
   
    return render(request, "category_add.html")
 