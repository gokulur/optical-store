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
    return render(request, 'adminpanel/categories/list.html', context)




# @login_required
# @user_passes_test(is_admin)
def add_category_page(request):
    """Add new category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        product_type = request.POST.get('product_type')
        parent_id = request.POST.get('parent')
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        # Handle image upload
        image = request.FILES.get('image')
        
        parent = None
        if parent_id:
            parent = Category.objects.get(id=parent_id)
        
        category = Category.objects.create(
            name=name,
            slug=slug,
            description=description,
            product_type=product_type,
            parent=parent,
            display_order=display_order,
            is_active=is_active,
            image=image
        )
        
        messages.success(request, f'Category "{name}" created successfully!')
        return redirect('adminpanel:category_list')
    
    # GET request
    parent_categories = Category.objects.filter(parent__isnull=True)
    
    context = {
        'parent_categories': parent_categories,
    }
    return render(request, 'adminpanel/categories/add.html', context)
 
 
# @login_required
# @user_passes_test(is_admin)
def category_edit(request, category_id):
    """Edit category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.slug = request.POST.get('slug')
        category.description = request.POST.get('description', '')
        category.product_type = request.POST.get('product_type')
        
        parent_id = request.POST.get('parent')
        category.parent = Category.objects.get(id=parent_id) if parent_id else None
        
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        
        if 'image' in request.FILES:
            category.image = request.FILES['image']
        
        category.save()
        
        messages.success(request, f'Category "{category.name}" updated successfully!')
        return redirect('adminpanel:category_list')
    
    parent_categories = Category.objects.filter(parent__isnull=True).exclude(id=category_id)
    
    context = {
        'category': category,
        'parent_categories': parent_categories,
    }
    return render(request, 'adminpanel/categories/edit.html', context)


# @login_required
# @user_passes_test(is_admin)
def category_delete(request, category_id):
    """Delete category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted successfully!')
        return redirect('adminpanel:category_list')
    
    context = {'category': category}
    return render(request, 'adminpanel/categories/delete_confirm.html', context)



# ==================== BRANDS ====================

# @login_required
# @user_passes_test(is_admin)
def brand_list(request):
    """List all brands"""
    search = request.GET.get('search', '')
    
    brands = Brand.objects.all().order_by('display_order', 'name')
    
    if search:
        brands = brands.filter(name__icontains=search)
    
    paginator = Paginator(brands, 25)
    page = request.GET.get('page', 1)
    brands = paginator.get_page(page)
    
    context = {
        'brands': brands,
        'search': search,
    }
    return render(request, 'adminpanel/brands/list.html', context)


# @login_required
# @user_passes_test(is_admin)
def brand_add(request):
    """Add new brand"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        logo = request.FILES.get('logo')
        
        available_for_sunglasses = request.POST.get('available_for_sunglasses') == 'on'
        available_for_eyeglasses = request.POST.get('available_for_eyeglasses') == 'on'
        available_for_kids = request.POST.get('available_for_kids') == 'on'
        available_for_contact_lenses = request.POST.get('available_for_contact_lenses') == 'on'
        
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        brand = Brand.objects.create(
            name=name,
            slug=slug,
            description=description,
            logo=logo,
            available_for_sunglasses=available_for_sunglasses,
            available_for_eyeglasses=available_for_eyeglasses,
            available_for_kids=available_for_kids,
            available_for_contact_lenses=available_for_contact_lenses,
            display_order=display_order,
            is_active=is_active
        )
        
        messages.success(request, f'Brand "{name}" created successfully!')
        return redirect('adminpanel:brand_list')
    
    return render(request, 'adminpanel/brands/add.html')


# @login_required
# @user_passes_test(is_admin)
def brand_edit(request, brand_id):
    """Edit brand"""
    brand = get_object_or_404(Brand, id=brand_id)
    
    if request.method == 'POST':
        brand.name = request.POST.get('name')
        brand.slug = request.POST.get('slug')
        brand.description = request.POST.get('description', '')
        
        if 'logo' in request.FILES:
            brand.logo = request.FILES['logo']
        
        brand.available_for_sunglasses = request.POST.get('available_for_sunglasses') == 'on'
        brand.available_for_eyeglasses = request.POST.get('available_for_eyeglasses') == 'on'
        brand.available_for_kids = request.POST.get('available_for_kids') == 'on'
        brand.available_for_contact_lenses = request.POST.get('available_for_contact_lenses') == 'on'
        
        brand.display_order = request.POST.get('display_order', 0)
        brand.is_active = request.POST.get('is_active') == 'on'
        
        brand.save()
        
        messages.success(request, f'Brand "{brand.name}" updated successfully!')
        return redirect('adminpanel:brand_list')
    
    context = {'brand': brand}
    return render(request, 'adminpanel/brands/edit.html', context)


# @login_required
# @user_passes_test(is_admin)
def brand_delete(request, brand_id):
    """Delete brand"""
    brand = get_object_or_404(Brand, id=brand_id)
    
    if request.method == 'POST':
        name = brand.name
        brand.delete()
        messages.success(request, f'Brand "{name}" deleted successfully!')
        return redirect('adminpanel:brand_list')
    
    context = {'brand': brand}
    return render(request, 'adminpanel/brands/delete_confirm.html', context)