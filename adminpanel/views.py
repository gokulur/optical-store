# adminpanel/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, F, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db import transaction, IntegrityError

# Models - Consolidated Imports
from catalog.models import (
    Category, Brand, Product, ProductVariant, ProductImage,
    ProductSpecification, ContactLensProduct, ContactLensColor,
    ContactLensPowerOption, ProductTag, ProductTagRelation
)
from lenses.models import (
    LensCategory, LensOption, LensAddOn, LensOptionAddOn,
    SunglassLensOption
)
from orders.models import Order, OrderItem
from users.models import User
from content.models import EyeTestBooking
from reviews.models import Review
from django.db.models import Count
# Helper: Check if admin
def is_admin(user):
    return user.is_authenticated and user.user_type in ['admin', 'staff']


# ==================== DASHBOARD ====================

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)

    total_revenue = (
        Order.objects
        .filter(payment_status='paid')
        .aggregate(total=Sum('total_amount'))['total']
        or Decimal('0.00')
    )

    monthly_income = (
        Order.objects
        .filter(payment_status='paid', created_at__date__gte=first_day_of_month)
        .aggregate(total=Sum('total_amount'))['total']
        or Decimal('0.00')
    )

    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()

    total_products = Product.objects.filter(is_active=True).count()
    low_stock_products = Product.objects.filter(
        track_inventory=True,
        stock_quantity__lte=5,
        stock_quantity__gt=0
    ).count()
    out_of_stock = Product.objects.filter(
        track_inventory=True,
        stock_quantity=0
    ).count()

 
    recent_orders = (
        Order.objects
        .select_related('customer')
        .annotate(items_count=Count('items'))
        .order_by('-created_at')[:5]
    )

    pending_bookings = EyeTestBooking.objects.filter(status='pending').count()

    context = {
        'revenue': total_revenue,
        'monthly_income': monthly_income,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock': out_of_stock,
        'recent_orders': recent_orders,
        'pending_bookings': pending_bookings,
    }

    return render(request, 'admin-dashboard.html', context)



# ==================== CATEGORIES ====================

@login_required
@user_passes_test(is_admin)
def category_list(request):
    search = request.GET.get('search', '')
    categories = Category.objects.all().order_by('display_order', 'name')
    
    if search:
        categories = categories.filter(Q(name__icontains=search))
    
    paginator = Paginator(categories, 25)
    page = request.GET.get('page', 1)
    categories = paginator.get_page(page)
    
    return render(request, 'adminpanel/categories/list.html', {'categories': categories, 'search': search})

@login_required
@user_passes_test(is_admin)
def category_add(request):
    if request.method == 'POST':
        try:
            Category.objects.create(
                name=request.POST.get('name'),
                slug=request.POST.get('slug'),
                description=request.POST.get('description', ''),
                parent=Category.objects.get(id=request.POST.get('parent')) if request.POST.get('parent') else None,
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
                image=request.FILES.get('image'),
                
                # Technical Flags
                has_prescription=request.POST.get('has_prescription') == 'True',
                has_lens_selection=request.POST.get('has_lens_selection') == 'True',
                has_power=request.POST.get('has_power') == 'True',
                has_color_variants=request.POST.get('has_color_variants') == 'True',
                has_size_variants=request.POST.get('has_size_variants') == 'True'
            )
            messages.success(request, 'Category created successfully!')
            return redirect('adminpanel:category_list')
        except IntegrityError:
            messages.error(request, 'Category slug already exists.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    parent_categories = Category.objects.filter(parent__isnull=True)
    return render(request, 'adminpanel/categories/add.html', {'parent_categories': parent_categories})

@login_required
@user_passes_test(is_admin)
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.slug = request.POST.get('slug')
        category.description = request.POST.get('description', '')
        category.parent = Category.objects.get(id=request.POST.get('parent')) if request.POST.get('parent') else None
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        
        if request.POST.get('remove_image') == '1': 
            category.image = None
        if 'image' in request.FILES: 
            category.image = request.FILES['image']
        
        # Flags
        category.has_prescription = request.POST.get('has_prescription') == 'True'
        category.has_lens_selection = request.POST.get('has_lens_selection') == 'True'
        category.has_power = request.POST.get('has_power') == 'True'
        category.has_color_variants = request.POST.get('has_color_variants') == 'True'
        category.has_size_variants = request.POST.get('has_size_variants') == 'True'

        category.save()
        messages.success(request, 'Category updated!')
        return redirect('adminpanel:category_list')

    parent_categories = Category.objects.filter(parent__isnull=True).exclude(id=category_id)
    return render(request, 'adminpanel/categories/edit.html', {'category': category, 'parent_categories': parent_categories})

@login_required
@user_passes_test(is_admin)
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('adminpanel:category_list')
    return render(request, 'adminpanel/categories/delete_confirm.html', {'category': category})


# ==================== BRANDS ====================

@login_required
@user_passes_test(is_admin)
def brand_list(request):
    search = request.GET.get('search', '')
    brands = Brand.objects.all().order_by('display_order', 'name')
    
    active_count = brands.filter(is_active=True).count()
    inactive_count = brands.filter(is_active=False).count()
    
    if search: 
        brands = brands.filter(name__icontains=search)
    
    paginator = Paginator(brands, 25)
    brands = paginator.get_page(request.GET.get('page', 1))
    
    return render(request, 'adminpanel/brands/list.html', {
        'brands': brands, 'search': search, 
        'active_count': active_count, 'inactive_count': inactive_count
    })

@login_required
@user_passes_test(is_admin)
def brand_add(request):
    if request.method == 'POST':
        try:
            Brand.objects.create(
                name=request.POST.get('name'),
                slug=request.POST.get('slug'),
                description=request.POST.get('description', ''),
                logo=request.FILES.get('logo'),
                available_for_sunglasses=request.POST.get('available_for_sunglasses') == 'on',
                available_for_eyeglasses=request.POST.get('available_for_eyeglasses') == 'on',
                available_for_kids=request.POST.get('available_for_kids') == 'on',
                available_for_contact_lenses=request.POST.get('available_for_contact_lenses') == 'on',
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Brand added!')
            return redirect('adminpanel:brand_list')
        except IntegrityError:
            messages.error(request, 'Brand name/slug exists.')
    return render(request, 'adminpanel/brands/add.html')

@login_required
@user_passes_test(is_admin)
def brand_edit(request, brand_id):
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
        messages.success(request, 'Brand updated!')
        return redirect('adminpanel:brand_list')
    return render(request, 'adminpanel/brands/edit.html', {'brand': brand})

@login_required
@user_passes_test(is_admin)
def brand_delete(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id)
    if request.method == 'POST':
        brand.delete()
        messages.success(request, 'Brand deleted.')
        return redirect('adminpanel:brand_list')
    return render(request, 'adminpanel/brands/delete_confirm.html', {'brand': brand})


# ==================== PRODUCTS ====================

@login_required
@user_passes_test(is_admin)
def product_list(request):
    search = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    brand_id = request.GET.get('brand', '')
    stock_status = request.GET.get('stock_status', '')

    products = Product.objects.select_related('brand', 'category').order_by('-created_at')

    # Stats
    total_count = Product.objects.count()
    low_stock_count = Product.objects.filter(track_inventory=True, stock_quantity__lte=5, stock_quantity__gt=0).count()
    out_of_stock_count = Product.objects.filter(track_inventory=True, stock_quantity=0).count()

    # Filters
    if search: 
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category_id: 
        products = products.filter(category_id=category_id)
    if brand_id: 
        products = products.filter(brand_id=brand_id)
    
    if stock_status == 'in_stock': 
        products = products.filter(stock_quantity__gt=5)
    elif stock_status == 'low_stock': 
        products = products.filter(stock_quantity__lte=5, stock_quantity__gt=0)
    elif stock_status == 'out_of_stock': 
        products = products.filter(stock_quantity=0)

    paginator = Paginator(products, 20)
    products = paginator.get_page(request.GET.get('page', 1))

    context = {
        'products': products,
        'categories': Category.objects.all(),
        'brands': Brand.objects.all(),
        'search': search, 
        'current_category': category_id, 
        'current_brand': brand_id,
        'stock_status': stock_status,
        'total_count': total_count, 
        'low_stock_count': low_stock_count, 
        'out_of_stock_count': out_of_stock_count
    }
    return render(request, 'adminpanel/products/list.html', context)

@login_required
@user_passes_test(is_admin)
def product_add(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Product
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
                    age_group=request.POST.get('age_group', 'adult'),
                    base_price=request.POST.get('base_price'),
                    compare_at_price=request.POST.get('compare_at_price') or None,
                    track_inventory=request.POST.get('track_inventory') == 'on',
                    stock_quantity=int(request.POST.get('stock_quantity') or 0),
                    is_active=request.POST.get('is_active') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                )

                # 2. Images
                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx==0))

                # 3. Variants
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')

                for sku, color, size, price, stock in zip(v_skus, v_colors, v_sizes, v_prices, v_stocks):
                    if sku.strip():
                        ProductVariant.objects.create(
                            product=product, variant_sku=sku, color_name=color, size=size,
                            price_adjustment=price or 0, stock_quantity=stock or 0
                        )

                # 4. Specs
                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')
                for key, val in zip(s_keys, s_values):
                    if key.strip():
                        ProductSpecification.objects.create(product=product, spec_key=key, spec_value=val)

                messages.success(request, 'Product added!')
                return redirect('adminpanel:product_list')
        except IntegrityError:
            messages.error(request, 'SKU or Slug exists.')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'brands': Brand.objects.filter(is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'product_types': Product.PRODUCT_TYPES
    }
    return render(request, 'adminpanel/products/add.html', context)

@login_required
@user_passes_test(is_admin)
def product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update Basic
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.product_type = request.POST.get('product_type')
                product.category_id = request.POST.get('category')
                product.brand_id = request.POST.get('brand') or None
                product.short_description = request.POST.get('short_description', '')
                product.description = request.POST.get('description', '')
                product.gender = request.POST.get('gender', 'unisex')
                product.age_group = request.POST.get('age_group', 'adult')
                product.base_price = request.POST.get('base_price')
                product.compare_at_price = request.POST.get('compare_at_price') or None
                product.track_inventory = request.POST.get('track_inventory') == 'on'
                product.stock_quantity = int(request.POST.get('stock_quantity') or 0)
                product.is_active = request.POST.get('is_active') == 'on'
                product.is_featured = request.POST.get('is_featured') == 'on'
                product.save()

                # Add New Images
                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)
                
                # Delete Images
                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()

                # Sync Variants
                v_ids = request.POST.getlist('variant_id[]')
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')

                kept_ids = []
                for i, sku in enumerate(v_skus):
                    if not sku.strip(): continue
                    vid = v_ids[i] if i < len(v_ids) else None
                    price = v_prices[i] or 0
                    stock = v_stocks[i] or 0
                    
                    if vid and vid != '0':
                        v = ProductVariant.objects.get(id=vid)
                        v.variant_sku=sku; v.color_name=v_colors[i]; v.size=v_sizes[i]; v.price_adjustment=price; v.stock_quantity=stock
                        v.save()
                        kept_ids.append(v.id)
                    else:
                        v = ProductVariant.objects.create(product=product, variant_sku=sku, color_name=v_colors[i], size=v_sizes[i], price_adjustment=price, stock_quantity=stock)
                        kept_ids.append(v.id)
                
                product.variants.exclude(id__in=kept_ids).delete()

                messages.success(request, 'Product updated!')
                return redirect('adminpanel:product_list')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'product': product,
        'brands': Brand.objects.filter(is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'product_types': Product.PRODUCT_TYPES,
        'images': product.images.all(),
        'variants': product.variants.all(),
        'specifications': product.specifications.all()
    }
    return render(request, 'adminpanel/products/edit.html', context)

@login_required
@user_passes_test(is_admin)
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('adminpanel:product_list')
    return render(request, 'adminpanel/products/delete_confirm.html', {'product': product})


# ==================== CONTACT LENSES ====================

@login_required
@user_passes_test(is_admin)
def contact_lens_list(request):
    search = request.GET.get('search', '')
    lens_type = request.GET.get('lens_type', '')
    
    lenses = ContactLensProduct.objects.select_related('product', 'product__brand').order_by('-product__created_at')
    
    if search:
        lenses = lenses.filter(
            Q(product__name__icontains=search) | 
            Q(product__sku__icontains=search)
        )
    if lens_type:
        lenses = lenses.filter(lens_type=lens_type)
    
    paginator = Paginator(lenses, 20)
    lenses = paginator.get_page(request.GET.get('page', 1))
    
    return render(request, 'adminpanel/contact_lenses/list.html', {
        'lenses': lenses,
        'search': search,
        'lens_type': lens_type
    })

@login_required
@user_passes_test(is_admin)
def contact_lens_add(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Create Product first
                product = Product.objects.create(
                    name=request.POST.get('name'),
                    sku=request.POST.get('sku'),
                    slug=request.POST.get('slug'),
                    product_type='contact_lenses',
                    category_id=request.POST.get('category'),
                    brand_id=request.POST.get('brand') or None,
                    description=request.POST.get('description', ''),
                    base_price=request.POST.get('base_price'),
                    track_inventory=True,
                    stock_quantity=int(request.POST.get('stock_quantity') or 0),
                    is_active=request.POST.get('is_active') == 'on',
                )
                
                # 2. Create ContactLensProduct
                contact_lens = ContactLensProduct.objects.create(
                    product=product,
                    lens_type=request.POST.get('lens_type'),
                    replacement_schedule=request.POST.get('replacement_schedule'),
                    package_size=request.POST.get('package_size'),
                    diameter=request.POST.get('diameter'),
                    base_curve=request.POST.get('base_curve'),
                    water_content=request.POST.get('water_content'),
                    intended_use=request.POST.get('intended_use', 'Vision / Cosmetic'),
                )
                
                # 3. Add images
                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx==0))
                
                messages.success(request, 'Contact Lens added!')
                return redirect('adminpanel:contact_lens_list')
        except IntegrityError:
            messages.error(request, 'SKU or Slug exists.')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'brands': Brand.objects.filter(available_for_contact_lenses=True, is_active=True)
    }
    return render(request, 'adminpanel/contact_lenses/add.html', context)

@login_required
@user_passes_test(is_admin)
def contact_lens_edit(request, lens_id):
    lens = get_object_or_404(ContactLensProduct.objects.select_related('product'), id=lens_id)
    product = lens.product
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update Product
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.brand_id = request.POST.get('brand') or None
                product.description = request.POST.get('description', '')
                product.base_price = request.POST.get('base_price')
                product.stock_quantity = int(request.POST.get('stock_quantity') or 0)
                product.is_active = request.POST.get('is_active') == 'on'
                product.save()
                
                # Update ContactLensProduct
                lens.lens_type = request.POST.get('lens_type')
                lens.replacement_schedule = request.POST.get('replacement_schedule')
                lens.package_size = request.POST.get('package_size')
                lens.diameter = request.POST.get('diameter')
                lens.base_curve = request.POST.get('base_curve')
                lens.water_content = request.POST.get('water_content')
                lens.intended_use = request.POST.get('intended_use', 'Vision / Cosmetic')
                lens.save()
                
                # Handle images
                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)
                
                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()
                
                messages.success(request, 'Contact Lens updated!')
                return redirect('adminpanel:contact_lens_list')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'lens': lens,
        'product': product,
        'brands': Brand.objects.filter(available_for_contact_lenses=True, is_active=True),
        'images': product.images.all()
    }
    return render(request, 'adminpanel/contact_lenses/edit.html', context)

@login_required
@user_passes_test(is_admin)
def contact_lens_delete(request, lens_id):
    lens = get_object_or_404(ContactLensProduct, id=lens_id)
    if request.method == 'POST':
        lens.product.delete()  # This will cascade delete ContactLensProduct
        messages.success(request, 'Contact Lens deleted.')
        return redirect('adminpanel:contact_lens_list')
    return render(request, 'adminpanel/contact_lenses/delete_confirm.html', {'lens': lens})


# ==================== CONTACT LENS COLORS ====================

@login_required
@user_passes_test(is_admin)
def contact_lens_color_list(request, lens_id):
    lens = get_object_or_404(ContactLensProduct, id=lens_id)
    colors = lens.colors.all().order_by('name')
    return render(request, 'adminpanel/contact_lenses/colors/list.html', {'lens': lens, 'colors': colors})

@login_required
@user_passes_test(is_admin)
def contact_lens_color_add(request, lens_id):
    lens = get_object_or_404(ContactLensProduct, id=lens_id)
    if request.method == 'POST':
        try:
            ContactLensColor.objects.create(
                contact_lens=lens,
                name=request.POST.get('name'),
                image=request.FILES.get('image'),
                power_enabled=request.POST.get('power_enabled') == 'on',
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Color added!')
            return redirect('adminpanel:contact_lens_color_list', lens_id=lens.id)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, 'adminpanel/contact_lenses/colors/add.html', {'lens': lens})

@login_required
@user_passes_test(is_admin)
def contact_lens_color_edit(request, color_id):
    color = get_object_or_404(ContactLensColor, id=color_id)
    if request.method == 'POST':
        color.name = request.POST.get('name')
        if 'image' in request.FILES:
            color.image = request.FILES['image']
        color.power_enabled = request.POST.get('power_enabled') == 'on'
        color.is_active = request.POST.get('is_active') == 'on'
        color.save()
        messages.success(request, 'Color updated!')
        return redirect('adminpanel:contact_lens_color_list', lens_id=color.contact_lens.id)
    return render(request, 'adminpanel/contact_lenses/colors/edit.html', {'color': color})

@login_required
@user_passes_test(is_admin)
def contact_lens_color_delete(request, color_id):
    color = get_object_or_404(ContactLensColor, id=color_id)
    lens_id = color.contact_lens.id
    if request.method == 'POST':
        color.delete()
        messages.success(request, 'Color deleted.')
    return redirect('adminpanel:contact_lens_color_list', lens_id=lens_id)


# ==================== LENS CATEGORIES ====================

@login_required
@user_passes_test(is_admin)
def lens_category_list(request):
    categories = LensCategory.objects.all().order_by('display_order')
    return render(request, 'adminpanel/lenses/categories/list.html', {'categories': categories})

@login_required
@user_passes_test(is_admin)
def lens_category_add(request):
    if request.method == 'POST':
        try:
            LensCategory.objects.create(
                name=request.POST.get('name'),
                category_type=request.POST.get('category_type'),
                description=request.POST.get('description', ''),
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Lens Category added!')
            return redirect('adminpanel:lens_category_list')
        except IntegrityError:
            messages.error(request, 'Category type already exists.')
        except Exception as e:
            messages.error(request, str(e))
    return render(request, 'adminpanel/lenses/categories/add.html', {
        'category_types': LensCategory.CATEGORY_TYPES
    })

@login_required
@user_passes_test(is_admin)
def lens_category_edit(request, cat_id):
    category = get_object_or_404(LensCategory, id=cat_id)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.category_type = request.POST.get('category_type')
        category.description = request.POST.get('description', '')
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        category.save()
        messages.success(request, 'Lens Category updated!')
        return redirect('adminpanel:lens_category_list')
    return render(request, 'adminpanel/lenses/categories/edit.html', {
        'category': category,
        'category_types': LensCategory.CATEGORY_TYPES
    })

@login_required
@user_passes_test(is_admin)
def lens_category_delete(request, cat_id):
    category = get_object_or_404(LensCategory, id=cat_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Lens Category deleted.')
        return redirect('adminpanel:lens_category_list')
    return render(request, 'adminpanel/lenses/categories/delete_confirm.html', {'category': category})


# ==================== LENS OPTIONS ====================

@login_required
@user_passes_test(is_admin)
def lens_option_list(request):
    category_id = request.GET.get('category', '')
    search = request.GET.get('search', '')
    
    options = LensOption.objects.select_related('category').order_by('category__display_order', 'display_order')
    
    if category_id:
        options = options.filter(category_id=category_id)
    if search:
        options = options.filter(Q(name__icontains=search) | Q(code__icontains=search))
    
    paginator = Paginator(options, 20)
    options = paginator.get_page(request.GET.get('page', 1))
    
    return render(request, 'adminpanel/lenses/options/list.html', {
        'options': options,
        'categories': LensCategory.objects.all(),
        'current_category': category_id,
        'search': search
    })

@login_required
@user_passes_test(is_admin)
def lens_option_add(request):
    if request.method == 'POST':
        try:
            features = request.POST.getlist('features[]')
            reading_powers = request.POST.getlist('reading_powers[]')
            
            LensOption.objects.create(
                category_id=request.POST.get('category'),
                name=request.POST.get('name'),
                code=request.POST.get('code'),
                description=request.POST.get('description', ''),
                base_price=request.POST.get('base_price'),
                lens_index=request.POST.get('lens_index'),
                material=request.POST.get('material', ''),
                features=features,
                min_sphere_power=request.POST.get('min_sphere_power') or None,
                max_sphere_power=request.POST.get('max_sphere_power') or None,
                min_cylinder_power=request.POST.get('min_cylinder_power') or None,
                max_cylinder_power=request.POST.get('max_cylinder_power') or None,
                available_reading_powers=reading_powers,
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
                is_premium=request.POST.get('is_premium') == 'on'
            )
            messages.success(request, 'Lens Option added!')
            return redirect('adminpanel:lens_option_list')
        except IntegrityError:
            messages.error(request, 'Code already exists.')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/options/add.html', {
        'categories': LensCategory.objects.filter(is_active=True)
    })

@login_required
@user_passes_test(is_admin)
def lens_option_edit(request, option_id):
    option = get_object_or_404(LensOption, id=option_id)
    if request.method == 'POST':
        try:
            features = request.POST.getlist('features[]')
            reading_powers = request.POST.getlist('reading_powers[]')
            
            option.category_id = request.POST.get('category')
            option.name = request.POST.get('name')
            option.code = request.POST.get('code')
            option.description = request.POST.get('description', '')
            option.base_price = request.POST.get('base_price')
            option.lens_index = request.POST.get('lens_index')
            option.material = request.POST.get('material', '')
            option.features = features
            option.min_sphere_power = request.POST.get('min_sphere_power') or None
            option.max_sphere_power = request.POST.get('max_sphere_power') or None
            option.min_cylinder_power = request.POST.get('min_cylinder_power') or None
            option.max_cylinder_power = request.POST.get('max_cylinder_power') or None
            option.available_reading_powers = reading_powers
            option.display_order = request.POST.get('display_order', 0)
            option.is_active = request.POST.get('is_active') == 'on'
            option.is_premium = request.POST.get('is_premium') == 'on'
            option.save()
            
            messages.success(request, 'Lens Option updated!')
            return redirect('adminpanel:lens_option_list')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/options/edit.html', {
        'option': option,
        'categories': LensCategory.objects.filter(is_active=True)
    })

@login_required
@user_passes_test(is_admin)
def lens_option_delete(request, option_id):
    option = get_object_or_404(LensOption, id=option_id)
    if request.method == 'POST':
        option.delete()
        messages.success(request, 'Lens Option deleted.')
        return redirect('adminpanel:lens_option_list')
    return render(request, 'adminpanel/lenses/options/delete_confirm.html', {'option': option})


# ==================== LENS ADD-ONS ====================

@login_required
@user_passes_test(is_admin)
def lens_addon_list(request):
    addons = LensAddOn.objects.all().order_by('name')
    return render(request, 'adminpanel/lenses/addons/list.html', {'addons': addons})

@login_required
@user_passes_test(is_admin)
def lens_addon_add(request):
    if request.method == 'POST':
        try:
            LensAddOn.objects.create(
                name=request.POST.get('name'),
                addon_type=request.POST.get('addon_type'),
                code=request.POST.get('code'),
                description=request.POST.get('description', ''),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Add-on created!')
            return redirect('adminpanel:lens_addon_list')
        except IntegrityError:
            messages.error(request, 'Code already exists.')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/addons/add.html', {
        'addon_types': LensAddOn.ADDON_TYPES
    })

@login_required
@user_passes_test(is_admin)
def lens_addon_edit(request, addon_id):
    addon = get_object_or_404(LensAddOn, id=addon_id)
    if request.method == 'POST':
        addon.name = request.POST.get('name')
        addon.addon_type = request.POST.get('addon_type')
        addon.code = request.POST.get('code')
        addon.description = request.POST.get('description', '')
        addon.is_active = request.POST.get('is_active') == 'on'
        addon.save()
        messages.success(request, 'Add-on updated!')
        return redirect('adminpanel:lens_addon_list')
    
    return render(request, 'adminpanel/lenses/addons/edit.html', {
        'addon': addon,
        'addon_types': LensAddOn.ADDON_TYPES
    })

@login_required
@user_passes_test(is_admin)
def lens_addon_delete(request, addon_id):
    addon = get_object_or_404(LensAddOn, id=addon_id)
    if request.method == 'POST':
        addon.delete()
        messages.success(request, 'Add-on deleted.')
        return redirect('adminpanel:lens_addon_list')
    return render(request, 'adminpanel/lenses/addons/delete_confirm.html', {'addon': addon})


# ==================== LENS OPTION ADD-ONS (Pricing) ====================

@login_required
@user_passes_test(is_admin)
def lens_option_addon_manage(request, option_id):
    lens_option = get_object_or_404(LensOption, id=option_id)
    existing_addons = lens_option.available_addons.all()
    all_addons = LensAddOn.objects.filter(is_active=True)
    
    if request.method == 'POST':
        try:
            # Clear existing
            lens_option.available_addons.all().delete()
            
            # Add new
            addon_ids = request.POST.getlist('addon_id[]')
            prices = request.POST.getlist('price[]')
            display_orders = request.POST.getlist('display_order[]')
            
            for addon_id, price, order in zip(addon_ids, prices, display_orders):
                if addon_id and price:
                    LensOptionAddOn.objects.create(
                        lens_option=lens_option,
                        addon_id=addon_id,
                        price=price,
                        display_order=order or 0
                    )
            
            messages.success(request, 'Add-ons updated!')
            return redirect('adminpanel:lens_option_list')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/option_addons/manage.html', {
        'lens_option': lens_option,
        'existing_addons': existing_addons,
        'all_addons': all_addons
    })


# ==================== SUNGLASS LENS OPTIONS ====================

@login_required
@user_passes_test(is_admin)
def sunglass_lens_list(request):
    options = SunglassLensOption.objects.all().order_by('display_order')
    return render(request, 'adminpanel/lenses/sunglass/list.html', {'options': options})

@login_required
@user_passes_test(is_admin)
def sunglass_lens_add(request):
    if request.method == 'POST':
        try:
            features = request.POST.getlist('features[]')
            SunglassLensOption.objects.create(
                lens_type=request.POST.get('lens_type'),
                name=request.POST.get('name'),
                base_price=request.POST.get('base_price'),
                lens_index=request.POST.get('lens_index', 1.56),
                features=features,
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Sunglass lens option added!')
            return redirect('adminpanel:sunglass_lens_list')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/sunglass/add.html', {
        'lens_types': SunglassLensOption.LENS_TYPES
    })

@login_required
@user_passes_test(is_admin)
def sunglass_lens_edit(request, option_id):
    option = get_object_or_404(SunglassLensOption, id=option_id)
    if request.method == 'POST':
        try:
            features = request.POST.getlist('features[]')
            option.lens_type = request.POST.get('lens_type')
            option.name = request.POST.get('name')
            option.base_price = request.POST.get('base_price')
            option.lens_index = request.POST.get('lens_index', 1.56)
            option.features = features
            option.display_order = request.POST.get('display_order', 0)
            option.is_active = request.POST.get('is_active') == 'on'
            option.save()
            messages.success(request, 'Sunglass lens option updated!')
            return redirect('adminpanel:sunglass_lens_list')
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'adminpanel/lenses/sunglass/edit.html', {
        'option': option,
        'lens_types': SunglassLensOption.LENS_TYPES
    })

@login_required
@user_passes_test(is_admin)
def sunglass_lens_delete(request, option_id):
    option = get_object_or_404(SunglassLensOption, id=option_id)
    if request.method == 'POST':
        option.delete()
        messages.success(request, 'Sunglass lens option deleted.')
        return redirect('adminpanel:sunglass_lens_list')
    return render(request, 'adminpanel/lenses/sunglass/delete_confirm.html', {'option': option})


# ==================== ORDERS ====================

@login_required
@user_passes_test(is_admin)
def order_list(request):
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    payment_status = request.GET.get('payment_status', '')
    
    orders = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')
    
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) | 
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search)
        )
    if status:
        orders = orders.filter(status=status)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    
    paginator = Paginator(orders, 20)
    orders = paginator.get_page(request.GET.get('page', 1))
    
    # Stats
    total_orders = Order.objects.count()
    pending_count = Order.objects.filter(status='pending').count()
    completed_count = Order.objects.filter(status='completed').count()
    
    return render(request, 'adminpanel/orders/list.html', {
        'orders': orders,
        'search': search,
        'status': status,
        'payment_status': payment_status,
        'total_orders': total_orders,
        'pending_count': pending_count,
        'completed_count': completed_count
    })

@login_required
@user_passes_test(is_admin)
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'items__variant'), 
        id=order_id
    )
    return render(request, 'adminpanel/orders/detail.html', {'order': order})

@login_required
@user_passes_test(is_admin)
def order_update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        order.status = request.POST.get('status')
        order.save()
        messages.success(request, f'Order status updated to {order.get_status_display()}!')
        return redirect('adminpanel:order_detail', order_id=order.id)
    return redirect('adminpanel:order_detail', order_id=order.id)

@login_required
@user_passes_test(is_admin)
def order_update_payment_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        order.payment_status = request.POST.get('payment_status')
        order.save()
        messages.success(request, f'Payment status updated!')
        return redirect('adminpanel:order_detail', order_id=order.id)
    return redirect('adminpanel:order_detail', order_id=order.id)


# ==================== EYE TEST BOOKINGS ====================

@login_required
@user_passes_test(is_admin)
def eye_test_list(request):
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    bookings = EyeTestBooking.objects.select_related('user').order_by('-booking_date', '-booking_time')
    
    if status:
        bookings = bookings.filter(status=status)
    if search:
        bookings = bookings.filter(
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(phone__icontains=search)
        )
    
    paginator = Paginator(bookings, 20)
    bookings = paginator.get_page(request.GET.get('page', 1))
    
    # Stats
    pending_count = EyeTestBooking.objects.filter(status='pending').count()
    confirmed_count = EyeTestBooking.objects.filter(status='confirmed').count()
    
    return render(request, 'adminpanel/eye_tests/list.html', {
        'bookings': bookings,
        'status': status,
        'search': search,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count
    })

@login_required
@user_passes_test(is_admin)
def eye_test_detail(request, booking_id):
    booking = get_object_or_404(EyeTestBooking, id=booking_id)
    if request.method == 'POST':
        booking.status = request.POST.get('status')
        booking.admin_notes = request.POST.get('admin_notes', '')
        booking.save()
        messages.success(request, 'Booking updated!')
        return redirect('adminpanel:eye_test_list')
    return render(request, 'adminpanel/eye_tests/detail.html', {'booking': booking})

@login_required
@user_passes_test(is_admin)
def eye_test_delete(request, booking_id):
    booking = get_object_or_404(EyeTestBooking, id=booking_id)
    if request.method == 'POST':
        booking.delete()
        messages.success(request, 'Booking deleted.')
        return redirect('adminpanel:eye_test_list')
    return render(request, 'adminpanel/eye_tests/delete_confirm.html', {'booking': booking})


# ==================== REVIEWS ====================

@login_required
@user_passes_test(is_admin)
def review_list(request):
    status = request.GET.get('status', '')
    
    reviews = Review.objects.select_related('user', 'product').order_by('-created_at')
    
    if status == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status == 'pending':
        reviews = reviews.filter(is_approved=False)
    
    paginator = Paginator(reviews, 20)
    reviews = paginator.get_page(request.GET.get('page', 1))
    
    # Stats
    total_count = Review.objects.count()
    pending_count = Review.objects.filter(is_approved=False).count()
    approved_count = Review.objects.filter(is_approved=True).count()
    
    return render(request, 'adminpanel/reviews/list.html', {
        'reviews': reviews,
        'status': status,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count
    })

@login_required
@user_passes_test(is_admin)
def review_approve(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = True
    review.save()
    messages.success(request, 'Review approved!')
    return redirect('adminpanel:review_list')

@login_required
@user_passes_test(is_admin)
def review_reject(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = False
    review.save()
    messages.success(request, 'Review rejected!')
    return redirect('adminpanel:review_list')

@login_required
@user_passes_test(is_admin)
def review_delete(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Review deleted.')
        return redirect('adminpanel:review_list')
    return render(request, 'adminpanel/reviews/delete_confirm.html', {'review': review})


# ==================== USERS ====================

@login_required
@user_passes_test(is_admin)
def user_list(request):
    search = request.GET.get('search', '')
    user_type = request.GET.get('user_type', '')
    
    users = User.objects.all().order_by('-date_joined')
    
    if search:
        users = users.filter(
            Q(email__icontains=search) | 
            Q(first_name__icontains=search) | 
            Q(last_name__icontains=search)
        )
    if user_type:
        users = users.filter(user_type=user_type)
    
    paginator = Paginator(users, 20)
    users = paginator.get_page(request.GET.get('page', 1))
    
    # Stats
    total_users = User.objects.count()
    customer_count = User.objects.filter(user_type='customer').count()
    admin_count = User.objects.filter(user_type__in=['admin', 'staff']).count()
    
    return render(request, 'adminpanel/users/list.html', {
        'users': users,
        'search': search,
        'user_type': user_type,
        'total_users': total_users,
        'customer_count': customer_count,
        'admin_count': admin_count
    })

@login_required
@user_passes_test(is_admin)
def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    orders = Order.objects.filter(user=user).order_by('-created_at')[:10]
    reviews = Review.objects.filter(user=user).order_by('-created_at')[:5]
    
    return render(request, 'adminpanel/users/detail.html', {
        'user_obj': user,
        'orders': orders,
        'reviews': reviews
    })

@login_required
@user_passes_test(is_admin)
def user_toggle_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {status}!')
    return redirect('adminpanel:user_detail', user_id=user.id)


# ==================== PRODUCT TAGS ====================

@login_required
@user_passes_test(is_admin)
def tag_list(request):
    tags = ProductTag.objects.annotate(product_count=Count('tagged_products')).order_by('name')
    return render(request, 'adminpanel/tags/list.html', {'tags': tags})

@login_required
@user_passes_test(is_admin)
def tag_add(request):
    if request.method == 'POST':
        try:
            ProductTag.objects.create(
                name=request.POST.get('name'),
                slug=request.POST.get('slug')
            )
            messages.success(request, 'Tag created!')
            return redirect('adminpanel:tag_list')
        except IntegrityError:
            messages.error(request, 'Tag name/slug already exists.')
    return render(request, 'adminpanel/tags/add.html')

@login_required
@user_passes_test(is_admin)
def tag_edit(request, tag_id):
    tag = get_object_or_404(ProductTag, id=tag_id)
    if request.method == 'POST':
        tag.name = request.POST.get('name')
        tag.slug = request.POST.get('slug')
        tag.save()
        messages.success(request, 'Tag updated!')
        return redirect('adminpanel:tag_list')
    return render(request, 'adminpanel/tags/edit.html', {'tag': tag})

@login_required
@user_passes_test(is_admin)
def tag_delete(request, tag_id):
    tag = get_object_or_404(ProductTag, id=tag_id)
    if request.method == 'POST':
        tag.delete()
        messages.success(request, 'Tag deleted.')
        return redirect('adminpanel:tag_list')
    return render(request, 'adminpanel/tags/delete_confirm.html', {'tag': tag})