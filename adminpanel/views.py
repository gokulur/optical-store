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
from django.db import transaction, IntegrityError
from catalog.models import (
    Category, Brand, Product, ProductVariant, ProductImage,
    ProductSpecification, ContactLensProduct, ContactLensPowerOption,
    ProductTag, ProductTagRelation,LensType
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

# @login_required
# @user_passes_test(is_admin)
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


# @login_required
# @user_passes_test(is_admin)
# adminpanel/views.py
 
def category_add(request):
    """Add new category with Technical Flags"""
    if request.method == 'POST':
        # 1. Basic Information
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        display_order = request.POST.get('display_order', 0)
        
        # 2. Checkbox & Image
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')

        # 3. Handle Parent Category
        parent_id = request.POST.get('parent')
        parent = None
        if parent_id:
            try:
                parent = Category.objects.get(id=parent_id)
            except Category.DoesNotExist:
                parent = None

        # 4. ✅ NEW: CAPTURE HIDDEN FLAGS (From your Template)
        # HTML form sends 'True' as a string, so we check if it equals 'True'
        has_prescription = request.POST.get('has_prescription') == 'True'
        has_lens_selection = request.POST.get('has_lens_selection') == 'True'
        has_power = request.POST.get('has_power') == 'True'
        has_color_variants = request.POST.get('has_color_variants') == 'True'
        has_size_variants = request.POST.get('has_size_variants') == 'True'

        try:
            # 5. Create the Category with Flags
            Category.objects.create(
                name=name,
                slug=slug,
                description=description,
                parent=parent,
                display_order=display_order,
                is_active=is_active,
                image=image,
                
                # ✅ Saving the Technical Configurations
                has_prescription=has_prescription,
                has_lens_selection=has_lens_selection,
                has_power=has_power,
                has_color_variants=has_color_variants,
                has_size_variants=has_size_variants
            )

            messages.success(request, f'Category "{name}" created successfully!')
            return redirect('adminpanel:category_list')

        except IntegrityError:
            messages.error(request, f'Error: A category with slug "{slug}" already exists.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')

    # GET Request
    parent_categories = Category.objects.filter(parent__isnull=True).order_by('name')
    
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
        # 1. Basic Info
        category.name = request.POST.get('name')
        category.slug = request.POST.get('slug')
        category.description = request.POST.get('description', '')
        
        # 2. Parent Category
        parent_id = request.POST.get('parent')
        if parent_id:
            category.parent = Category.objects.get(id=parent_id)
        else:
            category.parent = None
        
        # 3. Display & Active
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        
        # 4. Image Handling
        if request.POST.get('remove_image') == '1':
            category.image = None
        if 'image' in request.FILES:
            category.image = request.FILES['image']
            
      
        category.has_prescription = request.POST.get('has_prescription') == 'True'
        category.has_lens_selection = request.POST.get('has_lens_selection') == 'True'
        category.has_power = request.POST.get('has_power') == 'True'
        category.has_color_variants = request.POST.get('has_color_variants') == 'True'
        category.has_size_variants = request.POST.get('has_size_variants') == 'True'

        try:
            category.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('adminpanel:category_list')
        except Exception as e:
            messages.error(request, f"Error updating category: {str(e)}")
    
    # GET Request
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
    """List all brands with stats"""
    search = request.GET.get('search', '')
    
    # Base Query
    brands_queryset = Brand.objects.all().order_by('display_order', 'name')
    
    # Calculate Stats (Before filtering for search)
    active_count = brands_queryset.filter(is_active=True).count()
    inactive_count = brands_queryset.filter(is_active=False).count()
    
    # Apply Search Filter
    if search:
        brands_queryset = brands_queryset.filter(name__icontains=search)
    
    # Pagination
    paginator = Paginator(brands_queryset, 25)
    page = request.GET.get('page', 1)
    brands = paginator.get_page(page)
    
    context = {
        'brands': brands,
        'search': search,
        'active_count': active_count,    
        'inactive_count': inactive_count,  
    }
    return render(request, 'adminpanel/brands/list.html', context)


# @login_required
# @user_passes_test(is_admin)
def brand_add(request):
    """Add new brand with error handling"""
    if request.method == 'POST':
        # 1. Capture Data
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        logo = request.FILES.get('logo')
        
        # 2. Availability Flags
        available_for_sunglasses = request.POST.get('available_for_sunglasses') == 'on'
        available_for_eyeglasses = request.POST.get('available_for_eyeglasses') == 'on'
        available_for_kids = request.POST.get('available_for_kids') == 'on'
        available_for_contact_lenses = request.POST.get('available_for_contact_lenses') == 'on'
        
        # 3. Settings
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            # 4. Create Brand
            Brand.objects.create(
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

        except IntegrityError:
            # This catches duplicate Names or Slugs
            messages.error(request, f'Error: A brand with the name "{name}" or slug "{slug}" already exists.')
        except Exception as e:
            # This catches generic errors (like missing image)
            messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'adminpanel/brands/add.html')


# @login_required
# @user_passes_test(is_admin)
def brand_edit(request, brand_id):
    """Edit brand"""
    brand = get_object_or_404(Brand, id=brand_id)
    
    if request.method == 'POST':
        # 1. Basic Info
        brand.name = request.POST.get('name')
        brand.slug = request.POST.get('slug')
        brand.description = request.POST.get('description', '')
        
        # 2. Handle Logo (Only update if a new file is uploaded)
        if 'logo' in request.FILES:
            brand.logo = request.FILES['logo']
        
        # 3. Availability Flags
        # Checkboxes send 'on' if checked, otherwise nothing
        brand.available_for_sunglasses = request.POST.get('available_for_sunglasses') == 'on'
        brand.available_for_eyeglasses = request.POST.get('available_for_eyeglasses') == 'on'
        brand.available_for_kids = request.POST.get('available_for_kids') == 'on'
        brand.available_for_contact_lenses = request.POST.get('available_for_contact_lenses') == 'on'
        
        # 4. Display & Active
        brand.display_order = request.POST.get('display_order', 0)
        brand.is_active = request.POST.get('is_active') == 'on'
        
        try:
            brand.save()
            messages.success(request, f'Brand "{brand.name}" updated successfully!')
            return redirect('adminpanel:brand_list')
        except IntegrityError:
            messages.error(request, f'Error: Brand name or slug already exists.')
        except Exception as e:
            messages.error(request, f'Error updating brand: {str(e)}')
            
    return render(request, 'adminpanel/brands/edit.html', {'brand': brand})


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



# ==================== PRODUCTS ====================

# @login_required
# @user_passes_test(is_admin)
# adminpanel/views.py
 
def product_list(request):
    """List all products with advanced filtering and stats"""
    
    # 1. Get Filter Parameters
    search = request.GET.get('search', '')
    product_type = request.GET.get('product_type', '')
    brand_id = request.GET.get('brand', '')
    category_id = request.GET.get('category', '')
    stock_status = request.GET.get('stock_status', '')

    # 2. Base Queryset
    products_queryset = Product.objects.select_related('brand', 'category').prefetch_related('images').order_by('-created_at')

    # 3. Calculate Global Stats
    total_products = Product.objects.count()
    
    # ✅ FIX: Used fixed number '5' instead of F('low_stock_threshold')
    low_stock_count = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=5, 
        stock_quantity__gt=0
    ).count()
    
    out_of_stock_count = Product.objects.filter(
        track_inventory=True, 
        stock_quantity=0
    ).count()

    # 4. Apply Filters
    if search:
        products_queryset = products_queryset.filter(
            Q(name__icontains=search) | 
            Q(sku__icontains=search) |
            Q(description__icontains=search)
        )
    
    if product_type:
        products_queryset = products_queryset.filter(product_type=product_type)
    
    if brand_id:
        products_queryset = products_queryset.filter(brand_id=brand_id)
    
    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)
    
    # ✅ FIX: Updated Stock Filter Logic with fixed number '5'
    if stock_status == 'in_stock':
        products_queryset = products_queryset.filter(stock_quantity__gt=5)
    elif stock_status == 'low_stock':
        products_queryset = products_queryset.filter(
            track_inventory=True,
            stock_quantity__lte=5,
            stock_quantity__gt=0
        )
    elif stock_status == 'out_of_stock':
        products_queryset = products_queryset.filter(track_inventory=True, stock_quantity=0)

    # 5. Pagination
    paginator = Paginator(products_queryset, 20)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)
    
    # 6. Context Data
    brands = Brand.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    context = {
        'products': products,
        'brands': brands,
        'categories': categories,
        'search': search,
        'current_category': category_id, # Make sure these match template variables
        'current_brand': brand_id,
        'stock_status': stock_status,
        'total_count': total_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'adminpanel/products/list.html', context)


 


# @login_required
# @user_passes_test(is_admin)
def product_add(request):
    """Add new product with Images, Variants, and Specs"""
    if request.method == 'POST':
        try:
            with transaction.atomic():  # Start transaction
                
                # --- 1. HANDLE NUMERIC FIELDS SAFELY ---
                # Empty strings cause errors in DecimalFields, convert to None or 0
                compare_at_price = request.POST.get('compare_at_price')
                compare_at_price = compare_at_price if compare_at_price else None
                
                cost_price = request.POST.get('cost_price')
                cost_price = cost_price if cost_price else None

                stock_quantity = request.POST.get('stock_quantity')
                stock_quantity = int(stock_quantity) if stock_quantity else 0

                # --- 2. CREATE BASIC PRODUCT ---
                product = Product.objects.create(
                    name=request.POST.get('name'),
                    sku=request.POST.get('sku'),
                    slug=request.POST.get('slug'),
                    product_type=request.POST.get('product_type'),
                    category_id=request.POST.get('category'),
                    brand_id=request.POST.get('brand') or None,
                    
                    short_description=request.POST.get('short_description', ''),
                    description=request.POST.get('description', ''),
                    
                    gender=request.POST.get('gender', 'unisex'),
                    base_price=request.POST.get('base_price'),
                    compare_at_price=compare_at_price,
                    # cost_price=cost_price, # Uncomment if you added this field to model
                    
                    track_inventory=request.POST.get('track_inventory') == 'on',
                    stock_quantity=stock_quantity,
                    
                    is_active=request.POST.get('is_active') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                    
                    # SEO Fields (If added to model)
                    # meta_title=request.POST.get('meta_title', ''),
                    # meta_description=request.POST.get('meta_description', ''),
                )

                # --- 3. HANDLE IMAGES ---
                images = request.FILES.getlist('images')
                for index, img in enumerate(images):
                    ProductImage.objects.create(
                        product=product,
                        image=img,
                        is_primary=(index == 0) # Set first uploaded image as primary
                    )

                # --- 4. HANDLE DYNAMIC VARIANTS ---
                # Get lists from HTML array inputs: name="variant_sku[]"
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')

                # Zip them together to iterate row by row
                for sku, color, size, price, stock in zip(v_skus, v_colors, v_sizes, v_prices, v_stocks):
                    if sku.strip():  # Only create if SKU exists
                        ProductVariant.objects.create(
                            product=product,
                            variant_sku=sku,
                            color_name=color,
                            size=size,
                            price_adjustment=price if price else 0,
                            stock_quantity=stock if stock else 0
                        )

                # --- 5. HANDLE DYNAMIC SPECIFICATIONS ---
                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')

                for key, value in zip(s_keys, s_values):
                    if key.strip() and value.strip():
                        ProductSpecification.objects.create(
                            product=product,
                            spec_key=key,
                            spec_value=value
                        )

                messages.success(request, f'Product "{product.name}" added successfully!')
                return redirect('adminpanel:product_list')

        except IntegrityError as e:
            if 'unique constraint' in str(e).lower():
                messages.error(request, "Error: Product Name, SKU, or Slug already exists.")
            else:
                messages.error(request, f"Database Error: {str(e)}")
        except Exception as e:
            messages.error(request, f"Something went wrong: {str(e)}")

    # --- GET REQUEST: PREPARE FORM DATA ---
    context = {
        'brands': Brand.objects.filter(is_active=True).order_by('name'),
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'product_types': Product.PRODUCT_TYPES,
    }
    return render(request, 'adminpanel/products/add.html', context)


# @login_required
# @user_passes_test(is_admin)
def product_edit(request, product_id):
    """Edit existing product with Sync Logic (Create/Update/Delete child rows)"""
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                
                # --- 1. UPDATE BASIC INFO ---
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.product_type = request.POST.get('product_type')
                
                # Foreign Keys
                cat_id = request.POST.get('category')
                product.category = Category.objects.get(id=cat_id) if cat_id else None
                
                brand_id = request.POST.get('brand')
                product.brand = Brand.objects.get(id=brand_id) if brand_id else None

                # Text Fields
                product.short_description = request.POST.get('short_description', '')
                product.description = request.POST.get('description', '')
                product.gender = request.POST.get('gender', 'unisex')

                # Numeric Fields (Handle empty strings)
                product.base_price = request.POST.get('base_price') or 0
                product.compare_at_price = request.POST.get('compare_at_price') or None
                # product.cost_price = request.POST.get('cost_price') or None 
                
                # Inventory
                product.track_inventory = request.POST.get('track_inventory') == 'on'
                stock_qty = request.POST.get('stock_quantity')
                product.stock_quantity = int(stock_qty) if stock_qty else 0
                
                # Status
                product.is_active = request.POST.get('is_active') == 'on'
                product.is_featured = request.POST.get('is_featured') == 'on'
                
                product.save()

                # --- 2. HANDLE IMAGES ---
                # A. Add New Images
                new_images = request.FILES.getlist('images')
                for img in new_images:
                    ProductImage.objects.create(product=product, image=img)
                
                # B. Delete Removed Images
                # We expect a hidden input "delete_image_ids" containing "1,5,8"
                delete_img_ids = request.POST.get('delete_image_ids', '')
                if delete_img_ids:
                    ids_to_delete = [int(i) for i in delete_img_ids.split(',') if i.isdigit()]
                    ProductImage.objects.filter(id__in=ids_to_delete, product=product).delete()

                # --- 3. SYNC VARIANTS (Create/Update/Delete) ---
                # Get lists from form
                v_ids = request.POST.getlist('variant_id[]') # Hidden ID field
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')

                kept_variant_ids = []

                for i, sku in enumerate(v_skus):
                    if not sku.strip(): continue # Skip empty rows

                    vid = v_ids[i] if i < len(v_ids) else None # Get ID if exists
                    
                    price_adj = v_prices[i] if v_prices[i] else 0
                    stock_qty = v_stocks[i] if v_stocks[i] else 0

                    if vid and vid != '0':
                        # UPDATE Existing
                        variant = ProductVariant.objects.get(id=vid)
                        variant.variant_sku = sku
                        variant.color_name = v_colors[i]
                        variant.size = v_sizes[i]
                        variant.price_adjustment = price_adj
                        variant.stock_quantity = stock_qty
                        variant.save()
                        kept_variant_ids.append(variant.id)
                    else:
                        # CREATE New
                        new_var = ProductVariant.objects.create(
                            product=product,
                            variant_sku=sku,
                            color_name=v_colors[i],
                            size=v_sizes[i],
                            price_adjustment=price_adj,
                            stock_quantity=stock_qty
                        )
                        kept_variant_ids.append(new_var.id)

                # DELETE Variants not in the form anymore
                product.variants.exclude(id__in=kept_variant_ids).delete()

                # --- 4. SYNC SPECIFICATIONS ---
                s_ids = request.POST.getlist('spec_id[]')
                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')

                kept_spec_ids = []

                for i, key in enumerate(s_keys):
                    if not key.strip(): continue

                    sid = s_ids[i] if i < len(s_ids) else None

                    if sid and sid != '0':
                        spec = ProductSpecification.objects.get(id=sid)
                        spec.spec_key = key
                        spec.spec_value = s_values[i]
                        spec.save()
                        kept_spec_ids.append(spec.id)
                    else:
                        new_spec = ProductSpecification.objects.create(
                            product=product,
                            spec_key=key,
                            spec_value=s_values[i]
                        )
                        kept_spec_ids.append(new_spec.id)

                product.specifications.exclude(id__in=kept_spec_ids).delete()

                messages.success(request, f'Product "{product.name}" updated successfully!')
                return redirect('adminpanel:product_list')

        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")

    # --- GET REQUEST ---
    context = {
        'product': product,
        'brands': Brand.objects.filter(is_active=True).order_by('name'),
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'product_types': Product.PRODUCT_TYPES,
        
        # We pass related objects directly in template using product.variants.all
        # But images need distinct handling if you want to show primary first
        'images': product.images.all().order_by('-is_primary', 'id'),
        'variants': product.variants.all(),
        'specifications': product.specifications.all(),
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



# ==================== LENS MANAGEMENT ====================

# @login_required
# @user_passes_test(is_admin)
def lens_list(request):
    """List all Lens options"""
    lenses = LensType.objects.select_related('category', 'brand').order_by('category', 'price')
    lenses = "test"
    context = {
        'lenses': lenses,
    }
    return render(request, 'adminpanel/lenses/list.html', context)

# @login_required
# @user_passes_test(is_admin)
def lens_add(request):
    """Add a new Lens Package"""
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        index = request.POST.get('index')
        material = request.POST.get('material')
        price = request.POST.get('price')
        
        # Prescription Limits
        sph_min = request.POST.get('sph_min')
        sph_max = request.POST.get('sph_max')
        cyl_min = request.POST.get('cyl_min')
        cyl_max = request.POST.get('cyl_max')

        try:
            LensType.objects.create(
                name=name,
                category_id=category_id,
                brand_id=brand_id if brand_id else None,
                index=index,
                material=material,
                price=price,
                sph_min=sph_min,
                sph_max=sph_max,
                cyl_min=cyl_min,
                cyl_max=cyl_max
            )
            messages.success(request, f'Lens "{name}" added successfully!')
            return redirect('adminpanel:lens_list')
        except Exception as e:
            messages.error(request, f"Error adding lens: {str(e)}")

    # GET Request
    categories = LensCategory.objects.all()
    brands = Brand.objects.filter(is_active=True) # Assuming you use same Brand model or separate LensBrand
    
    context = {
        'categories': categories,
        'brands': brands,
    }
    return render(request, 'adminpanel/lenses/add.html', context)


@login_required
@user_passes_test(is_admin)
def lens_edit(request, lens_id):
    """Edit existing Lens Package"""
    lens = get_object_or_404(LensType, id=lens_id)

    if request.method == 'POST':
        try:
            # 1. Update Basic Info
            lens.name = request.POST.get('name')
            lens.category_id = request.POST.get('category')
            
            brand_id = request.POST.get('brand')
            lens.brand_id = brand_id if brand_id else None
            
            # 2. Update Specs
            lens.index = request.POST.get('index')
            lens.material = request.POST.get('material')
            lens.price = request.POST.get('price')

            # 3. Update Power Limits
            lens.sph_min = request.POST.get('sph_min')
            lens.sph_max = request.POST.get('sph_max')
            lens.cyl_min = request.POST.get('cyl_min')
            lens.cyl_max = request.POST.get('cyl_max')

            lens.save()
            messages.success(request, f'Lens "{lens.name}" updated successfully!')
            return redirect('adminpanel:lens_list')

        except Exception as e:
            messages.error(request, f"Error updating lens: {str(e)}")

    # GET Request
    categories = LensCategory.objects.all()
    brands = Brand.objects.filter(is_active=True)
    
    context = {
        'lens': lens,
        'categories': categories,
        'brands': brands,
    }
    return render(request, 'adminpanel/lenses/edit.html', context)

# @login_required
# @user_passes_test(is_admin)
def lens_delete(request, lens_id):
    lens = get_object_or_404(LensType, id=lens_id)
    if request.method == 'POST':
        lens.delete()
        messages.success(request, 'Lens package deleted successfully.')
        return redirect('adminpanel:lens_list')
    




# ==================== LENS CATEGORIES ====================

# @login_required
# @user_passes_test(is_admin)
def lens_category_list(request):
    """List all Lens Categories (Single Vision, Progressive etc.)"""
    categories = LensCategory.objects.all().order_by('name')
    return render(request, 'adminpanel/lens-category/list.html', {'categories': categories})

# @login_required
# @user_passes_test(is_admin)
def lens_category_add(request):
    """Add a new Lens Category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description')

        try:
            LensCategory.objects.create(name=name, slug=slug, description=description)
            messages.success(request, f'Lens Category "{name}" added!')
            return redirect('adminpanel:lens_category_list')
        except IntegrityError:
            messages.error(request, "Category with this slug already exists.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    return render(request, 'adminpanel/lens-category/add.html')

# @login_required
# @user_passes_test(is_admin)
def lens_category_delete(request, cat_id):
    cat = get_object_or_404(LensCategory, id=cat_id)
    if request.method == 'POST':
        cat.delete()
        messages.success(request, "Lens Category deleted.")
    return redirect('adminpanel:lens_category_list')