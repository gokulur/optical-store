# adminpanel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

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
    yesterday = today - timedelta(days=1)
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    first_day_of_month = today.replace(day=1)
    
    # ============ REVENUE CALCULATIONS ============
    
    # Total Revenue (all time)
    total_revenue = Order.objects.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Monthly Income (current month)
    monthly_income = Order.objects.filter(
        payment_status='paid',
        created_at__date__gte=first_day_of_month
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Daily Income (today)
    daily_income = Order.objects.filter(
        payment_status='paid',
        created_at__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Yesterday's Income
    yesterday_income = Order.objects.filter(
        payment_status='paid',
        created_at__date=yesterday
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Week income
    week_income = Order.objects.filter(
        payment_status='paid',
        created_at__date__gte=last_7_days
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # ============ SALES CALCULATIONS ============
    
    # Total items sold (all time)
    total_sales = OrderItem.objects.filter(
        order__payment_status='paid'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Monthly sales
    monthly_sales = OrderItem.objects.filter(
        order__payment_status='paid',
        order__created_at__date__gte=first_day_of_month
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Daily sales
    daily_sales = OrderItem.objects.filter(
        order__payment_status='paid',
        order__created_at__date=today
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # ============ ORDER STATISTICS ============
    
    # Total orders
    total_orders = Order.objects.count()
    
    # Orders by status
    pending_orders = Order.objects.filter(status='pending').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    processing_orders = Order.objects.filter(status='processing').count()
    shipped_orders = Order.objects.filter(status='shipped').count()
    delivered_orders = Order.objects.filter(status='delivered').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    
    # Today's orders
    today_orders = Order.objects.filter(created_at__date=today).count()
    
    # Monthly orders
    month_orders = Order.objects.filter(created_at__date__gte=first_day_of_month).count()
    
    # ============ PRODUCT STATISTICS ============
    
    # Total products
    total_products = Product.objects.filter(is_active=True).count()
    
    # Products by type
    sunglasses_count = Product.objects.filter(product_type='sunglasses', is_active=True).count()
    eyeglasses_count = Product.objects.filter(product_type='eyeglasses', is_active=True).count()
    contact_lenses_count = Product.objects.filter(product_type='contact_lenses', is_active=True).count()
    accessories_count = Product.objects.filter(product_type='accessories', is_active=True).count()
    
    # Low stock products (stock_quantity <= 5)
    low_stock_products = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=5,
        stock_quantity__gt=0,
        is_active=True
    ).count()
    
    # Out of stock
    out_of_stock = Product.objects.filter(
        track_inventory=True,
        stock_quantity=0,
        is_active=True
    ).count()
    
    # Featured products
    featured_products = Product.objects.filter(is_featured=True, is_active=True).count()
    
    # ============ CUSTOMER STATISTICS ============
    
    # Total customers
    total_customers = User.objects.filter(user_type='customer').count()
    
    # New customers this month
    new_customers_month = User.objects.filter(
        user_type='customer',
        created_at__date__gte=first_day_of_month
    ).count()
    
    # New customers today
    new_customers_today = User.objects.filter(
        user_type='customer',
        created_at__date=today
    ).count()
    
    # ============ RECENT DATA ============
    
    # Recent orders (last 10)
    recent_orders = Order.objects.select_related(
        'customer'
    ).prefetch_related('items').order_by('-created_at')[:10]
    
    # Top selling products (by stock quantity - as proxy for sales since no sales_count field)
    top_products = Product.objects.filter(
        is_active=True
    ).order_by('-stock_quantity')[:5]
    
    # Recent customers
    recent_customers = User.objects.filter(
        user_type='customer'
    ).order_by('-created_at')[:5]
    
    # ============ REVIEWS & RATINGS ============
    
    # Pending reviews
    pending_reviews = Review.objects.filter(is_approved=False).count()
    
    # Total reviews
    total_reviews = Review.objects.count()
    
    # ============ BOOKINGS & ALERTS ============
    
    # Eye test bookings pending
    pending_bookings = EyeTestBooking.objects.filter(status='pending').count()
    
    # Today's bookings
    today_bookings = EyeTestBooking.objects.filter(booking_date=today).count()
    
    # ============ LOW STOCK ITEMS ============
    
    low_stock_items = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=5,
        stock_quantity__gt=0,
        is_active=True
    ).select_related('brand', 'category').order_by('stock_quantity')[:10]
    
    # ============ MONTHLY COMPARISON ============
    
    # Previous month
    previous_month_start = (first_day_of_month - timedelta(days=1)).replace(day=1)
    previous_month_end = first_day_of_month - timedelta(days=1)
    
    previous_month_income = Order.objects.filter(
        payment_status='paid',
        created_at__date__gte=previous_month_start,
        created_at__date__lte=previous_month_end
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Growth percentage
    if previous_month_income > 0:
        income_growth = ((monthly_income - previous_month_income) / previous_month_income) * 100
    else:
        income_growth = 100 if monthly_income > 0 else 0

    context = {
        # Revenue
        'revenue': total_revenue,
        'monthly_income': monthly_income,
        'daily_income': daily_income,
        'yesterday_income': yesterday_income,
        'week_income': week_income,
        'income_growth': round(income_growth, 2),
        
        # Sales
        'sales': total_sales,
        'monthly_sales': monthly_sales,
        'daily_sales': daily_sales,
        
        # Orders
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'today_orders': today_orders,
        'month_orders': month_orders,
        
        # Products
        'total_products': total_products,
        'sunglasses_count': sunglasses_count,
        'eyeglasses_count': eyeglasses_count,
        'contact_lenses_count': contact_lenses_count,
        'accessories_count': accessories_count,
        'low_stock_products': low_stock_products,
        'out_of_stock': out_of_stock,
        'featured_products': featured_products,
        
        # Customers
        'total_customers': total_customers,
        'new_customers_month': new_customers_month,
        'new_customers_today': new_customers_today,
        
        # Recent data
        'recent_orders': recent_orders,
        'top_products': top_products,
        'recent_customers': recent_customers,
        'low_stock_items': low_stock_items,
        
        # Reviews
        'pending_reviews': pending_reviews,
        'total_reviews': total_reviews,
        
        # Bookings
        'pending_bookings': pending_bookings,
        'today_bookings': today_bookings,
    }
    
    return render(request, 'admin-dashboard.html', context)


# ==================== CATEGORIES ====================

@login_required
@user_passes_test(is_admin)
def category_list(request):
    """List all categories"""
    search = request.GET.get('search', '')
    
    categories = Category.objects.all().order_by('display_order', 'name')
    
    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    paginator = Paginator(categories, 25)
    page = request.GET.get('page', 1)
    categories = paginator.get_page(page)
    
    context = {
        'categories': categories,
        'search': search,
    }
    return render(request, 'adminpanel/categories/list.html', context)


@login_required
@user_passes_test(is_admin)
def category_add(request):
    """Add new category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
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


@login_required
@user_passes_test(is_admin)
def category_edit(request, category_id):
    """Edit category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.slug = request.POST.get('slug')
        category.description = request.POST.get('description', '')
        
        parent_id = request.POST.get('parent')
        category.parent = Category.objects.get(id=parent_id) if parent_id else None
        
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        
        # Handle remove image
        if request.POST.get('remove_image') == '1':
            category.image = None
        
        # Handle new image upload
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


@login_required
@user_passes_test(is_admin)
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

@login_required
@user_passes_test(is_admin)
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


@login_required
@user_passes_test(is_admin)
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


@login_required
@user_passes_test(is_admin)
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


@login_required
@user_passes_test(is_admin)
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



# ==================== PRODUCTS ====================

# @login_required
# @user_passes_test(is_admin)
def product_list(request):
    """List all products"""
    search = request.GET.get('search', '')
    product_type = request.GET.get('product_type', '')
    brand_id = request.GET.get('brand', '')
    category_id = request.GET.get('category', '')
    is_active = request.GET.get('is_active', '')
    stock_status = request.GET.get('stock_status', '')
    
    products = Product.objects.select_related('brand', 'category').order_by('-created_at')
    
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(sku__icontains=search) |
            Q(description__icontains=search)
        )
    
    if product_type:
        products = products.filter(product_type=product_type)
    
    if brand_id:
        products = products.filter(brand_id=brand_id)
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if is_active:
        products = products.filter(is_active=(is_active == 'true'))
    
    if stock_status == 'low':
        products = products.filter(
            track_inventory=True,
            stock_quantity__lte=F('low_stock_threshold'),
            stock_quantity__gt=0
        )
    elif stock_status == 'out':
        products = products.filter(track_inventory=True, stock_quantity=0)
    
    paginator = Paginator(products, 25)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)
    
    # For filters
    brands = Brand.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    context = {
        'products': products,
        'brands': brands,
        'categories': categories,
        'search': search,
        'product_type': product_type,
        'brand_id': brand_id,
        'category_id': category_id,
        'is_active': is_active,
        'stock_status': stock_status,
    }
    return render(request, 'adminpanel/products/list.html', context)


# @login_required
# @user_passes_test(is_admin)
def product_add(request):
    """Add new product"""
    if request.method == 'POST':
        # Basic info
        sku = request.POST.get('sku')
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        product_type = request.POST.get('product_type')
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        
        # Description
        short_description = request.POST.get('short_description', '')
        description = request.POST.get('description', '')
        
        # Pricing
        base_price = request.POST.get('base_price')
        compare_at_price = request.POST.get('compare_at_price') or None
        cost_price = request.POST.get('cost_price') or None
        
        # Categorization
        gender = request.POST.get('gender', 'unisex')
        age_group = request.POST.get('age_group', 'adult')
        
        # Inventory
        track_inventory = request.POST.get('track_inventory') == 'on'
        stock_quantity = request.POST.get('stock_quantity', 0)
        low_stock_threshold = request.POST.get('low_stock_threshold', 5)
        allow_backorder = request.POST.get('allow_backorder') == 'on'
        
        # SEO
        meta_title = request.POST.get('meta_title', '')
        meta_description = request.POST.get('meta_description', '')
        meta_keywords = request.POST.get('meta_keywords', '')
        
        # Status
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        is_on_sale = request.POST.get('is_on_sale') == 'on'
        
        product = Product.objects.create(
            sku=sku,
            name=name,
            slug=slug,
            product_type=product_type,
            category_id=category_id,
            brand_id=brand_id if brand_id else None,
            short_description=short_description,
            description=description,
            base_price=base_price,
            compare_at_price=compare_at_price,
            cost_price=cost_price,
            gender=gender,
            age_group=age_group,
            track_inventory=track_inventory,
            stock_quantity=stock_quantity,
            low_stock_threshold=low_stock_threshold,
            allow_backorder=allow_backorder,
            meta_title=meta_title,
            meta_description=meta_description,
            meta_keywords=meta_keywords,
            is_active=is_active,
            is_featured=is_featured,
            is_on_sale=is_on_sale
        )
        
        messages.success(request, f'Product "{name}" created successfully!')
        return redirect('adminpanel:product_edit', product_id=product.id)
    
    # GET request
    brands = Brand.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    context = {
        'brands': brands,
        'categories': categories,
    }
    return render(request, 'adminpanel/products/add.html', context)


# @login_required
# @user_passes_test(is_admin)
def product_edit(request, product_id):
    """Edit product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # Update basic info
        product.sku = request.POST.get('sku')
        product.name = request.POST.get('name')
        product.slug = request.POST.get('slug')
        product.product_type = request.POST.get('product_type')
        product.category_id = request.POST.get('category')
        
        brand_id = request.POST.get('brand')
        product.brand_id = brand_id if brand_id else None
        
        product.short_description = request.POST.get('short_description', '')
        product.description = request.POST.get('description', '')
        
        product.base_price = request.POST.get('base_price')
        product.compare_at_price = request.POST.get('compare_at_price') or None
        product.cost_price = request.POST.get('cost_price') or None
        
        product.gender = request.POST.get('gender', 'unisex')
        product.age_group = request.POST.get('age_group', 'adult')
        
        product.track_inventory = request.POST.get('track_inventory') == 'on'
        product.stock_quantity = request.POST.get('stock_quantity', 0)
        product.low_stock_threshold = request.POST.get('low_stock_threshold', 5)
        product.allow_backorder = request.POST.get('allow_backorder') == 'on'
        
        product.meta_title = request.POST.get('meta_title', '')
        product.meta_description = request.POST.get('meta_description', '')
        product.meta_keywords = request.POST.get('meta_keywords', '')
        
        product.is_active = request.POST.get('is_active') == 'on'
        product.is_featured = request.POST.get('is_featured') == 'on'
        product.is_on_sale = request.POST.get('is_on_sale') == 'on'
        
        product.save()
        
        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('adminpanel:product_edit', product_id=product.id)
    
    # GET request
    brands = Brand.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Get related data
    variants = product.variants.all()
    images = product.images.all()
    specifications = product.specifications.all()
    
    # Check if contact lens
    contact_lens_details = None
    contact_lens_powers = []
    if product.product_type == 'contact_lenses':
        try:
            contact_lens_details = product.contact_lens_details
            contact_lens_powers = contact_lens_details.power_options.all()
        except ContactLensProduct.DoesNotExist:
            pass
    
    context = {
        'product': product,
        'brands': brands,
        'categories': categories,
        'variants': variants,
        'images': images,
        'specifications': specifications,
        'contact_lens_details': contact_lens_details,
        'contact_lens_powers': contact_lens_powers,
    }
    return render(request, 'adminpanel/products/edit.html', context)


# @login_required
# @user_passes_test(is_admin)
def product_delete(request, product_id):
    """Delete product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully!')
        return redirect('adminpanel:product_list')
    
    context = {'product': product}
    return render(request, 'adminpanel/products/delete_confirm.html', context)