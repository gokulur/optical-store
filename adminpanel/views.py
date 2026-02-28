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
from content.models import EyeTestBooking, StoreLocation, Banner
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import models
from jobs.models import JobOrder, JobStatusHistory, JobDocument
# Models - Consolidated Imports
from catalog.models import (
    Category, Brand, Product, ProductVariant, ProductImage,
    ProductSpecification, ContactLensProduct, ContactLensColor,
    ContactLensPowerOption, ProductTag, ProductTagRelation,
    LensOption, LensBrand, LensType
)
from lenses.models import (
    LensCategory, LensAddOn, LensOptionAddOn,
    SunglassLensOption
)
from lenses.models import LensOption as PrescriptionLensOption
from orders.models import Order, OrderItem
from users.models import User
from reviews.models import Review
from django.db.models import Count, Max
from django.http import JsonResponse
# Helper: Check if admin
def is_admin(user):
    return (
        user.is_authenticated and
        (
            user.is_superuser or
            user.is_staff or
            user.user_type in ['admin', 'staff']
        )
    )


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
                # Existing availability fields
                available_for_sunglasses=request.POST.get('available_for_sunglasses') == 'on',
                available_for_eyeglasses=request.POST.get('available_for_eyeglasses') == 'on',
                available_for_kids=request.POST.get('available_for_kids') == 'on',
                available_for_contact_lenses=request.POST.get('available_for_contact_lenses') == 'on',
                # New availability fields (checklist §2 & §3)
                available_for_reading_glasses=request.POST.get('available_for_reading_glasses') == 'on',
                available_for_medical_lenses=request.POST.get('available_for_medical_lenses') == 'on',
                available_for_accessories=request.POST.get('available_for_accessories') == 'on',
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Brand added!')
            return redirect('adminpanel:brand_list')
        except IntegrityError:
            messages.error(request, 'Brand name/slug exists.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
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

        # Existing availability fields
        brand.available_for_sunglasses = request.POST.get('available_for_sunglasses') == 'on'
        brand.available_for_eyeglasses = request.POST.get('available_for_eyeglasses') == 'on'
        brand.available_for_kids = request.POST.get('available_for_kids') == 'on'
        brand.available_for_contact_lenses = request.POST.get('available_for_contact_lenses') == 'on'
        # New availability fields (checklist §2 & §3)
        brand.available_for_reading_glasses = request.POST.get('available_for_reading_glasses') == 'on'
        brand.available_for_medical_lenses = request.POST.get('available_for_medical_lenses') == 'on'
        brand.available_for_accessories = request.POST.get('available_for_accessories') == 'on'

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

    total_count = Product.objects.count()
    low_stock_count = Product.objects.filter(track_inventory=True, stock_quantity__lte=5, stock_quantity__gt=0).count()
    out_of_stock_count = Product.objects.filter(track_inventory=True, stock_quantity=0).count()

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

                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx == 0))

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

                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)

                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()

                v_ids = request.POST.getlist('variant_id[]')
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')

                kept_ids = []
                for i, sku in enumerate(v_skus):
                    if not sku.strip():
                        continue
                    vid = v_ids[i] if i < len(v_ids) else None
                    price = v_prices[i] or 0
                    stock = v_stocks[i] or 0

                    if vid and vid != '0':
                        v = ProductVariant.objects.get(id=vid)
                        v.variant_sku = sku
                        v.color_name = v_colors[i]
                        v.size = v_sizes[i]
                        v.price_adjustment = price
                        v.stock_quantity = stock
                        v.save()
                        kept_ids.append(v.id)
                    else:
                        v = ProductVariant.objects.create(
                            product=product, variant_sku=sku, color_name=v_colors[i],
                            size=v_sizes[i], price_adjustment=price, stock_quantity=stock
                        )
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
                name = request.POST.get('name')
                sku = request.POST.get('sku')
                slug = request.POST.get('slug')
                category_id = request.POST.get('category')
                base_price = request.POST.get('base_price')

                if not all([name, sku, slug, category_id, base_price]):
                    messages.error(request, "Please fill all required fields.")
                    return redirect(request.path)

                product = Product.objects.create(
                    name=name, sku=sku, slug=slug,
                    product_type='contact_lenses',
                    category_id=int(category_id),
                    brand_id=request.POST.get('brand') or None,
                    description=request.POST.get('description', ''),
                    base_price=Decimal(base_price),
                    track_inventory=request.POST.get('track_inventory') == 'on',
                    stock_quantity=int(request.POST.get('stock_quantity') or 0),
                    is_active=request.POST.get('is_active') == 'on',
                )

                ContactLensProduct.objects.create(
                    product=product,
                    lens_type=request.POST.get('lens_type'),
                    replacement_schedule=request.POST.get('replacement_schedule'),
                    package_size=int(request.POST.get('package_size')),
                    diameter=Decimal(request.POST.get('diameter')),
                    base_curve=Decimal(request.POST.get('base_curve')),
                    water_content=Decimal(request.POST.get('water_content')),
                    intended_use=request.POST.get('intended_use', 'Vision / Cosmetic'),
                )

                for i, image in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=image, is_primary=(i == 0))

                messages.success(request, "Contact lens added successfully!")
                return redirect('adminpanel:contact_lens_list')

        except IntegrityError:
            messages.error(request, "SKU or Slug already exists.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    context = {
        'brands': Brand.objects.filter(available_for_contact_lenses=True, is_active=True),
        'categories': Category.objects.filter(is_active=True)
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
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.brand_id = request.POST.get('brand') or None
                product.description = request.POST.get('description', '')
                product.base_price = request.POST.get('base_price')
                product.stock_quantity = int(request.POST.get('stock_quantity') or 0)
                product.is_active = request.POST.get('is_active') == 'on'
                product.save()

                lens.lens_type = request.POST.get('lens_type')
                lens.replacement_schedule = request.POST.get('replacement_schedule')
                lens.package_size = request.POST.get('package_size')
                lens.diameter = request.POST.get('diameter')
                lens.base_curve = request.POST.get('base_curve')
                lens.water_content = request.POST.get('water_content')
                lens.intended_use = request.POST.get('intended_use', 'Vision / Cosmetic')
                lens.save()

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
        lens.product.delete()
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


# ==================== LENS CATEGORIES (Prescription/lenses app) ====================

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


# ==================== PRESCRIPTION LENS OPTIONS (lenses app) ====================

@login_required
@user_passes_test(is_admin)
def prescription_lens_option_list(request):
    category_id = request.GET.get('category', '')
    search = request.GET.get('search', '')

    options = PrescriptionLensOption.objects.select_related('category').order_by('category__display_order', 'display_order')

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
def prescription_lens_option_add(request):
    if request.method == 'POST':
        try:
            features = request.POST.getlist('features[]')
            reading_powers = request.POST.getlist('reading_powers[]')

            PrescriptionLensOption.objects.create(
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
            return redirect('adminpanel:prescription_lens_option_list')
        except IntegrityError:
            messages.error(request, 'Code already exists.')
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'adminpanel/lenses/options/add.html', {
        'categories': LensCategory.objects.filter(is_active=True)
    })


@login_required
@user_passes_test(is_admin)
def prescription_lens_option_edit(request, option_id):
    option = get_object_or_404(PrescriptionLensOption, id=option_id)
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
            return redirect('adminpanel:prescription_lens_option_list')
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'adminpanel/lenses/options/edit.html', {
        'option': option,
        'categories': LensCategory.objects.filter(is_active=True)
    })


@login_required
@user_passes_test(is_admin)
def prescription_lens_option_delete(request, option_id):
    option = get_object_or_404(PrescriptionLensOption, id=option_id)
    if request.method == 'POST':
        option.delete()
        messages.success(request, 'Lens Option deleted.')
        return redirect('adminpanel:prescription_lens_option_list')
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
    lens_option = get_object_or_404(PrescriptionLensOption, id=option_id)
    existing_addons = lens_option.available_addons.all()
    all_addons = LensAddOn.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            lens_option.available_addons.all().delete()

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
            return redirect('adminpanel:prescription_lens_option_list')
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


# ==================== MEDICAL LENS BRANDS (catalog app) ====================

@login_required
@user_passes_test(is_admin)
def lens_brand_list(request):
    search = request.GET.get('search', '')
    brands = LensBrand.objects.all().order_by('display_order', 'name')

    total_count = brands.count()
    active_count = brands.filter(is_active=True).count()
    inactive_count = brands.filter(is_active=False).count()

    if search:
        brands = brands.filter(name__icontains=search)

    paginator = Paginator(brands, 25)
    brands = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/medical/lens_brand_list.html', {
        'brands': brands,
        'search': search,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
    })


@login_required
@user_passes_test(is_admin)
def lens_brand_add(request):
    if request.method == 'POST':
        try:
            LensBrand.objects.create(
                name=request.POST.get('name'),
                slug=request.POST.get('slug'),
                description=request.POST.get('description', ''),
                logo=request.FILES.get('logo'),
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
            )
            messages.success(request, 'Lens brand created successfully!')
            return redirect('adminpanel:lens_brand_list')
        except IntegrityError:
            messages.error(request, 'Brand slug already exists.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return render(request, 'adminpanel/medical/lens_brand_add.html')


@login_required
@user_passes_test(is_admin)
def lens_brand_edit(request, brand_id):
    brand = get_object_or_404(LensBrand, id=brand_id)
    if request.method == 'POST':
        brand.name = request.POST.get('name')
        brand.slug = request.POST.get('slug')
        brand.description = request.POST.get('description', '')
        brand.display_order = request.POST.get('display_order', 0)
        brand.is_active = request.POST.get('is_active') == 'on'
        if 'logo' in request.FILES:
            brand.logo = request.FILES['logo']
        brand.save()
        messages.success(request, 'Lens brand updated!')
        return redirect('adminpanel:lens_brand_list')
    return render(request, 'adminpanel/medical/lens_brand_edit.html', {'brand': brand})


@login_required
@user_passes_test(is_admin)
def lens_brand_delete(request, brand_id):
    brand = get_object_or_404(LensBrand, id=brand_id)
    if request.method == 'POST':
        brand.delete()
        messages.success(request, 'Lens brand deleted.')
        return redirect('adminpanel:lens_brand_list')
    return redirect('adminpanel:lens_brand_list')


# ==================== LENS TYPES (per medical brand) ====================

@login_required
@user_passes_test(is_admin)
def lens_type_list(request, brand_id):
    brand = get_object_or_404(LensBrand, id=brand_id)
    types = LensType.objects.filter(lens_brand=brand).order_by('display_order', 'name')
    return render(request, 'adminpanel/medical/lens_type_list.html', {
        'brand': brand,
        'types': types,
    })


@login_required
@user_passes_test(is_admin)
def lens_type_add(request, brand_id):
    brand = get_object_or_404(LensBrand, id=brand_id)
    if request.method == 'POST':
        try:
            LensType.objects.create(
                lens_brand=brand,
                name=request.POST.get('name'),
                slug=request.POST.get('slug'),
                description=request.POST.get('description', ''),
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
            )
            messages.success(request, f'Lens type added to {brand.name}!')
            return redirect('adminpanel:lens_type_list', brand_id=brand.id)
        except IntegrityError:
            messages.error(request, 'Slug already exists for this brand.')
        except Exception as e:
            messages.error(request, str(e))
    return render(request, 'adminpanel/medical/lens_type_form.html', {'brand': brand})


@login_required
@user_passes_test(is_admin)
def lens_type_edit(request, type_id):
    lens_type = get_object_or_404(LensType, id=type_id)
    brand = lens_type.lens_brand
    if request.method == 'POST':
        lens_type.name = request.POST.get('name')
        lens_type.slug = request.POST.get('slug')
        lens_type.description = request.POST.get('description', '')
        lens_type.display_order = request.POST.get('display_order', 0)
        lens_type.is_active = request.POST.get('is_active') == 'on'
        lens_type.save()
        messages.success(request, 'Lens type updated!')
        return redirect('adminpanel:lens_type_list', brand_id=brand.id)
    return render(request, 'adminpanel/medical/lens_type_form.html', {
        'brand': brand,
        'lens_type': lens_type,
    })


@login_required
@user_passes_test(is_admin)
def lens_type_delete(request, type_id):
    lens_type = get_object_or_404(LensType, id=type_id)
    brand_id = lens_type.lens_brand_id
    if request.method == 'POST':
        lens_type.delete()
        messages.success(request, 'Lens type deleted.')
    return redirect('adminpanel:lens_type_list', brand_id=brand_id)


# ==================== MEDICAL LENS OPTIONS (catalog app LensOption) ====================

INDEX_CHOICES = [
    ("1.50", "1.50 (Standard)"),
    ("1.56", "1.56 (Mid-Index)"),
    ("1.60", "1.60 (Thin)"),
    ("1.67", "1.67 (Extra Thin)"),
    ("1.74", "1.74 (Ultra Thin)"),
]


@login_required
@user_passes_test(is_admin)
def medical_lens_list(request):
    queryset = LensOption.objects.select_related('lens_brand', 'lens_type').all()

    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(lens_brand__name__icontains=search) |
            Q(lens_type__name__icontains=search) |
            Q(index__icontains=search)
        )

    selected_lens_brands = request.GET.getlist('lens_brand')
    if selected_lens_brands:
        queryset = queryset.filter(lens_brand__slug__in=selected_lens_brands)

    selected_lens_types = request.GET.getlist('lens_type')
    if selected_lens_types:
        queryset = queryset.filter(lens_type__slug__in=selected_lens_types)

    selected_indexes = request.GET.getlist('index')
    if selected_indexes:
        queryset = queryset.filter(index__in=selected_indexes)

    sort_option = request.GET.get('sort', '-id')
    valid_sorts = ['-id', 'base_price', '-base_price', '-created_at']
    if sort_option not in valid_sorts:
        sort_option = '-id'
    queryset = queryset.order_by(sort_option)

    paginator = Paginator(queryset, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    index_options = (
        LensOption.objects
        .values_list('index', flat=True)
        .distinct()
        .order_by('index')
    )

    return render(request, 'adminpanel/medical/medical_lens_list.html', {
        'lens_options': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'lens_brands': LensBrand.objects.filter(is_active=True).order_by('name'),
        'lens_types': LensType.objects.filter(is_active=True).order_by('name'),
        'index_options': index_options,
        'selected_lens_brands': selected_lens_brands,
        'selected_lens_types': selected_lens_types,
        'selected_indexes': selected_indexes,
        'current_sort': sort_option,
        'search': search,
    })


@login_required
@user_passes_test(is_admin)
def medical_lens_add(request):
    if request.method == 'POST':
        lens_brand_id = request.POST.get('lens_brand')
        lens_type_id = request.POST.get('lens_type')
        index = request.POST.get('index', '').strip()
        base_price = request.POST.get('base_price')
        min_power = request.POST.get('min_power')
        max_power = request.POST.get('max_power')
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not lens_brand_id:
            errors.append("Please select a lens brand.")
        if not lens_type_id:
            errors.append("Please select a lens type.")
        if not index:
            errors.append("Please select a lens index.")
        if not base_price:
            errors.append("Base price is required.")
        if not min_power or not max_power:
            errors.append("Both minimum and maximum power are required.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                LensOption.objects.create(
                    lens_brand_id=lens_brand_id,
                    lens_type_id=lens_type_id,
                    index=index,
                    base_price=base_price,
                    min_power=min_power,
                    max_power=max_power,
                    is_active=is_active,
                )
                messages.success(request, "Lens option added successfully!")
                return redirect('adminpanel:medical_lens_list')
            except Exception as ex:
                messages.error(request, f"Error saving lens option: {ex}")

    return render(request, 'adminpanel/medical/medical_lens_add.html', {
        'lens_brands': LensBrand.objects.filter(is_active=True).order_by('name'),
        'lens_types': LensType.objects.filter(is_active=True).order_by('name'),
        'index_choices': INDEX_CHOICES,
        'available_coatings': LensAddOn.objects.filter(is_active=True),
    })


@login_required
@user_passes_test(is_admin)
def medical_lens_edit(request, option_id):
    lens_option = get_object_or_404(LensOption, pk=option_id)

    if request.method == 'POST':
        lens_brand_id = request.POST.get('lens_brand')
        lens_type_id = request.POST.get('lens_type')
        index = request.POST.get('index', '').strip()
        base_price = request.POST.get('base_price')
        min_power = request.POST.get('min_power')
        max_power = request.POST.get('max_power')
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not lens_brand_id:
            errors.append("Please select a lens brand.")
        if not lens_type_id:
            errors.append("Please select a lens type.")
        if not index:
            errors.append("Please select a lens index.")
        if not base_price:
            errors.append("Base price is required.")
        if not min_power or not max_power:
            errors.append("Both minimum and maximum power are required.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                lens_option.lens_brand_id = lens_brand_id
                lens_option.lens_type_id = lens_type_id
                lens_option.index = index
                lens_option.base_price = base_price
                lens_option.min_power = min_power
                lens_option.max_power = max_power
                lens_option.is_active = is_active
                lens_option.save()
                messages.success(request, "Lens option updated successfully!")
                return redirect('adminpanel:medical_lens_list')
            except Exception as ex:
                messages.error(request, f"Error updating lens option: {ex}")

    return render(request, 'adminpanel/medical/medical_lens_edit.html', {
        'lens_option': lens_option,
        'lens_brands': LensBrand.objects.filter(is_active=True).order_by('name'),
        'lens_types': LensType.objects.filter(is_active=True).order_by('name'),
        'index_choices': INDEX_CHOICES,
        'available_coatings': LensAddOn.objects.filter(is_active=True),
    })


@login_required
@user_passes_test(is_admin)
def medical_lens_delete(request, option_id):
    lens_option = get_object_or_404(LensOption, pk=option_id)
    if request.method == 'POST':
        lens_option.delete()
        messages.success(request, "Lens option deleted successfully.")
        return redirect('adminpanel:medical_lens_list')
    return redirect('adminpanel:medical_lens_list')


# ==================== ORDERS ====================

@login_required
@user_passes_test(is_admin)
def order_list(request):
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    payment_status = request.GET.get('payment_status', '')

    orders = Order.objects.select_related('customer').prefetch_related('items').order_by('-created_at')

    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(customer__email__icontains=search) |
            Q(customer__first_name__icontains=search)
        )
    if status:
        orders = orders.filter(status=status)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)

    paginator = Paginator(orders, 20)
    orders = paginator.get_page(request.GET.get('page', 1))

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
        messages.success(request, 'Payment status updated!')
        return redirect('adminpanel:order_detail', order_id=order.id)
    return redirect('adminpanel:order_detail', order_id=order.id)


# ==================== EYE TEST BOOKINGS ====================

@login_required
@user_passes_test(is_admin)
def eye_test_list(request):
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')

    bookings = EyeTestBooking.objects.select_related('customer').order_by('-booking_date', '-booking_time')

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

    reviews = Review.objects.select_related('customer', 'product').order_by('-created_at')

    if status == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status == 'pending':
        reviews = reviews.filter(is_approved=False)

    paginator = Paginator(reviews, 20)
    reviews = paginator.get_page(request.GET.get('page', 1))

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
    orders = Order.objects.filter(customer=user).order_by('-created_at')[:10]
    reviews = Review.objects.filter(customer=user).order_by('-created_at')[:5]

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


# ==================== STORE LOCATIONS ====================

DAYS_OF_WEEK = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]


@login_required
@user_passes_test(is_admin)
def store_list(request):
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    eye_test = request.GET.get('eye_test', '')

    stores = StoreLocation.objects.all().order_by('display_order', 'name')

    total_stores = stores.count()
    active_stores = stores.filter(is_active=True).count()
    flagship_stores = stores.filter(is_flagship=True).count()
    eye_test_stores = stores.filter(offers_eye_test=True).count()

    if search:
        stores = stores.filter(
            Q(name__icontains=search) |
            Q(city__icontains=search) |
            Q(address_line1__icontains=search)
        )
    if status == 'active':
        stores = stores.filter(is_active=True)
    elif status == 'inactive':
        stores = stores.filter(is_active=False)
    if eye_test == 'yes':
        stores = stores.filter(offers_eye_test=True)
    elif eye_test == 'no':
        stores = stores.filter(offers_eye_test=False)

    paginator = Paginator(stores, 20)
    stores = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/stores/list.html', {
        'stores': stores, 'search': search, 'status': status, 'eye_test': eye_test,
        'total_stores': total_stores, 'active_stores': active_stores,
        'flagship_stores': flagship_stores, 'eye_test_stores': eye_test_stores,
    })


@login_required
@user_passes_test(is_admin)
def store_add(request):
    if request.method == 'POST':
        try:
            operating_hours = {}
            for day_key, _ in DAYS_OF_WEEK:
                hours_value = request.POST.get(f'hours_{day_key}', '').strip()
                if hours_value:
                    operating_hours[day_key] = hours_value

            StoreLocation.objects.create(
                name=request.POST.get('name'),
                address_line1=request.POST.get('address_line1'),
                address_line2=request.POST.get('address_line2', ''),
                city=request.POST.get('city'),
                state=request.POST.get('state', ''),
                country=request.POST.get('country'),
                postal_code=request.POST.get('postal_code', ''),
                phone=request.POST.get('phone'),
                email=request.POST.get('email', ''),
                latitude=request.POST.get('latitude') or None,
                longitude=request.POST.get('longitude') or None,
                google_maps_url=request.POST.get('google_maps_url', ''),
                operating_hours=operating_hours,
                offers_eye_test=request.POST.get('offers_eye_test') == 'on',
                is_flagship=request.POST.get('is_flagship') == 'on',
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
            )
            messages.success(request, 'Store location created successfully!')
            return redirect('adminpanel:store_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'adminpanel/stores/add.html', {'days': DAYS_OF_WEEK})


@login_required
@user_passes_test(is_admin)
def store_edit(request, store_id):
    store = get_object_or_404(StoreLocation, id=store_id)

    if request.method == 'POST':
        try:
            operating_hours = {}
            for day_key, _ in DAYS_OF_WEEK:
                hours_value = request.POST.get(f'hours_{day_key}', '').strip()
                if hours_value:
                    operating_hours[day_key] = hours_value

            store.name = request.POST.get('name')
            store.address_line1 = request.POST.get('address_line1')
            store.address_line2 = request.POST.get('address_line2', '')
            store.city = request.POST.get('city')
            store.state = request.POST.get('state', '')
            store.country = request.POST.get('country')
            store.postal_code = request.POST.get('postal_code', '')
            store.phone = request.POST.get('phone')
            store.email = request.POST.get('email', '')
            store.latitude = request.POST.get('latitude') or None
            store.longitude = request.POST.get('longitude') or None
            store.google_maps_url = request.POST.get('google_maps_url', '')
            store.operating_hours = operating_hours
            store.offers_eye_test = request.POST.get('offers_eye_test') == 'on'
            store.is_flagship = request.POST.get('is_flagship') == 'on'
            store.display_order = request.POST.get('display_order', 0)
            store.is_active = request.POST.get('is_active') == 'on'
            store.save()

            messages.success(request, 'Store location updated successfully!')
            return redirect('adminpanel:store_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'adminpanel/stores/edit.html', {'store': store, 'days': DAYS_OF_WEEK})


@login_required
@user_passes_test(is_admin)
def store_delete(request, store_id):
    store = get_object_or_404(StoreLocation, id=store_id)
    if request.method == 'POST':
        store.delete()
        messages.success(request, 'Store location deleted.')
        return redirect('adminpanel:store_list')
    return render(request, 'adminpanel/stores/delete_confirm.html', {'store': store})


# ==================== LIVE CHAT ====================

from chat_support.models import (
    ChatConversation, ChatMessage, ChatQuickReply, AgentStatus
)


def _agent_status(request):
    try:
        return AgentStatus.objects.get(agent=request.user).status
    except AgentStatus.DoesNotExist:
        return 'offline'


@staff_member_required
def chat_list(request):
    qs = ChatConversation.objects.select_related('user', 'assigned_to').annotate(
        message_count=Count('messages'),
        last_message_time=Max('messages__created_at')
    )

    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    priority = request.GET.get('priority')
    if priority:
        qs = qs.filter(priority=priority)

    assigned = request.GET.get('assigned_to')
    if assigned == 'me':
        qs = qs.filter(assigned_to=request.user)
    elif assigned == 'unassigned':
        qs = qs.filter(assigned_to__isnull=True)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            models.Q(guest_name__icontains=search) |
            models.Q(guest_email__icontains=search) |
            models.Q(subject__icontains=search) |
            models.Q(user__email__icontains=search) |
            models.Q(user__first_name__icontains=search)
        )

    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    stats = {
        'total': ChatConversation.objects.count(),
        'open': ChatConversation.objects.filter(status='open').count(),
        'in_progress': ChatConversation.objects.filter(status='in_progress').count(),
        'unassigned': ChatConversation.objects.filter(assigned_to__isnull=True).count(),
    }

    return render(request, 'adminpanel/chat/list.html', {
        'conversations': page,
        'stats': stats,
        'agent_status': _agent_status(request),
    })


@staff_member_required
def chat_conversation(request, conversation_id):
    conversation = get_object_or_404(ChatConversation, conversation_id=conversation_id)

    conversation.messages.filter(
        is_from_customer=True, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    messages_qs = conversation.messages.all()
    quick_replies = ChatQuickReply.objects.filter(is_active=True)[:10]

    return render(request, 'adminpanel/chat/conversation.html', {
        'conversation': conversation,
        'messages': messages_qs,
        'quick_replies': quick_replies,
    })


@staff_member_required
@require_http_methods(["POST"])
def chat_agent_status(request):
    obj, _ = AgentStatus.objects.get_or_create(agent=request.user)
    obj.status = request.POST.get('status', 'offline')
    obj.save()
    return redirect('adminpanel:chat_list')


from chat_support.models import ChatMessage as CM


def admin_chat_context(request):
    if request.user.is_authenticated and request.user.is_staff:
        count = CM.objects.filter(
            is_from_customer=True,
            is_read=False
        ).values('conversation').distinct().count()
        return {'unread_chat_count': count}
    return {'unread_chat_count': 0}


# ==================== BANNERS ====================

@login_required
@user_passes_test(is_admin)
def banner_list(request):
    banner_type = request.GET.get('banner_type', '')
    placement = request.GET.get('placement', '')
    search = request.GET.get('search', '')

    banners = Banner.objects.all().order_by('placement', 'display_order')

    total_count = Banner.objects.count()
    active_count = Banner.objects.filter(is_active=True).count()
    inactive_count = Banner.objects.filter(is_active=False).count()
    scheduled_count = Banner.objects.filter(is_active=True, start_date__isnull=False).count()

    if banner_type:
        banners = banners.filter(banner_type=banner_type)
    if placement:
        banners = banners.filter(placement=placement)
    if search:
        banners = banners.filter(title__icontains=search)

    paginator = Paginator(banners, 20)
    banners = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/banners/list.html', {
        'banners': banners, 'banner_type': banner_type, 'placement': placement, 'search': search,
        'total_count': total_count, 'active_count': active_count,
        'inactive_count': inactive_count, 'scheduled_count': scheduled_count,
        'banner_types': Banner.BANNER_TYPES,
        'placement_choices': Banner.PLACEMENT_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def banner_add(request):
    if request.method == 'POST':
        try:
            Banner.objects.create(
                title=request.POST.get('title'),
                banner_type=request.POST.get('banner_type'),
                placement=request.POST.get('placement'),
                image_desktop=request.FILES.get('image_desktop'),
                image_mobile=request.FILES.get('image_mobile') or None,
                image_tablet=request.FILES.get('image_tablet') or None,
                link_url=request.POST.get('link_url', ''),
                link_type=request.POST.get('link_type', ''),
                linked_product_id=request.POST.get('linked_product_id') or None,
                start_date=request.POST.get('start_date') or None,
                end_date=request.POST.get('end_date') or None,
                display_order=request.POST.get('display_order', 0),
                is_active=request.POST.get('is_active') == 'on',
                auto_slide=request.POST.get('auto_slide') == 'on',
                slide_duration=request.POST.get('slide_duration', 5),
                slide_heading=request.POST.get('slide_heading', ''),
                slide_description=request.POST.get('slide_description', ''),
                cta_text=request.POST.get('cta_text', 'Read More'),
            )
            messages.success(request, 'Banner (slide) created successfully!')
            return redirect('adminpanel:banner_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    link_type_choices = [
        ('product', 'Product Page'), ('category', 'Category Page'),
        ('brand', 'Brand Page'), ('page', 'Static Page'), ('external', 'External URL'),
    ]
    return render(request, 'adminpanel/banners/add.html', {
        'banner_types': Banner.BANNER_TYPES,
        'placement_choices': Banner.PLACEMENT_CHOICES,
        'link_type_choices': link_type_choices,
    })


@login_required
@user_passes_test(is_admin)
def banner_edit(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)

    if request.method == 'POST':
        try:
            banner.title = request.POST.get('title')
            banner.banner_type = request.POST.get('banner_type')
            banner.placement = request.POST.get('placement')
            banner.link_url = request.POST.get('link_url', '')
            banner.link_type = request.POST.get('link_type', '')
            banner.linked_product_id = request.POST.get('linked_product_id') or None
            banner.start_date = request.POST.get('start_date') or None
            banner.end_date = request.POST.get('end_date') or None
            banner.display_order = request.POST.get('display_order', 0)
            banner.is_active = request.POST.get('is_active') == 'on'
            banner.auto_slide = request.POST.get('auto_slide') == 'on'
            banner.slide_duration = request.POST.get('slide_duration', 5)

            if request.FILES.get('image_desktop'):
                banner.image_desktop = request.FILES['image_desktop']
            if request.FILES.get('image_mobile'):
                banner.image_mobile = request.FILES['image_mobile']
            if request.FILES.get('image_tablet'):
                banner.image_tablet = request.FILES['image_tablet']
            if request.POST.get('remove_image_mobile') == '1':
                banner.image_mobile = None
            if request.POST.get('remove_image_tablet') == '1':
                banner.image_tablet = None

            banner.save()
            messages.success(request, 'Banner updated successfully!')
            return redirect('adminpanel:banner_list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    link_type_choices = [
        ('product', 'Product Page'), ('category', 'Category Page'),
        ('brand', 'Brand Page'), ('page', 'Static Page'), ('external', 'External URL'),
    ]
    return render(request, 'adminpanel/banners/edit.html', {
        'banner': banner,
        'banner_types': Banner.BANNER_TYPES,
        'placement_choices': Banner.PLACEMENT_CHOICES,
        'link_type_choices': link_type_choices,
    })


@login_required
@user_passes_test(is_admin)
def banner_delete(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    if request.method == 'POST':
        banner.delete()
        messages.success(request, 'Banner deleted.')
        return redirect('adminpanel:banner_list')
    return render(request, 'adminpanel/banners/delete_confirm.html', {'banner': banner})


@login_required
@user_passes_test(is_admin)
def banner_toggle_active(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    banner.is_active = not banner.is_active
    banner.save()
    status = 'activated' if banner.is_active else 'deactivated'
    messages.success(request, f'Slide "{banner.title}" {status}.')
    return redirect('adminpanel:banner_list')


# ==================== PROMOTIONS / COUPONS ====================

from promotions.models import Coupon, CouponUsage
from django.utils.dateparse import parse_datetime


@login_required
@user_passes_test(is_admin)
def coupon_list(request):
    search        = request.GET.get('search', '')
    discount_type = request.GET.get('discount_type', '')
    status        = request.GET.get('status', '')

    coupons = Coupon.objects.all().order_by('-created_at')

    if search:
        coupons = coupons.filter(Q(code__icontains=search) | Q(name__icontains=search))
    if discount_type:
        coupons = coupons.filter(discount_type=discount_type)

    now = timezone.now()
    if status == 'active':
        coupons = coupons.filter(is_active=True, valid_until__gte=now)
    elif status == 'expired':
        coupons = coupons.filter(valid_until__lt=now)
    elif status == 'inactive':
        coupons = coupons.filter(is_active=False)

    total_count  = Coupon.objects.count()
    active_count = Coupon.objects.filter(is_active=True, valid_until__gte=now).count()
    expired_count= Coupon.objects.filter(valid_until__lt=now).count()
    total_uses   = Coupon.objects.aggregate(t=Sum('times_used'))['t'] or 0

    paginator = Paginator(coupons, 20)
    coupons   = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/promotions/list.html', {
        'coupons':        coupons,
        'search':         search,
        'discount_type':  discount_type,
        'status':         status,
        'total_count':    total_count,
        'active_count':   active_count,
        'expired_count':  expired_count,
        'total_uses':     total_uses,
        'today':          now.date(),
    })


@login_required
@user_passes_test(is_admin)
def coupon_add(request):
    if request.method == 'POST':
        try:
            # ── FIX: datetime-local sends "YYYY-MM-DDTHH:MM" — Django's DateTimeField
            #    needs a timezone-aware datetime. We parse it and make it aware.
            def parse_dt(val):
                """Convert datetime-local string to timezone-aware datetime."""
                if not val:
                    return None
                # datetime-local format: "2025-06-01T00:00"
                dt = parse_datetime(val)
                if dt is None:
                    # fallback: try with seconds appended
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        return None
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt

            valid_from  = parse_dt(request.POST.get('valid_from'))
            valid_until = parse_dt(request.POST.get('valid_until'))

            if not valid_from or not valid_until:
                raise ValueError("Please provide both Valid From and Valid Until dates.")

            if valid_until <= valid_from:
                raise ValueError("Valid Until must be after Valid From.")

            discount_type = request.POST.get('discount_type', 'percentage')
            # free_shipping has no meaningful discount_value
            discount_value = request.POST.get('discount_value') or 0
            if discount_type == 'free_shipping':
                discount_value = 0

            Coupon.objects.create(
                code                    = request.POST.get('code', '').strip().upper(),
                name                    = request.POST.get('name'),
                description             = request.POST.get('description', ''),
                discount_type           = discount_type,
                discount_value          = discount_value,
                minimum_order_amount    = request.POST.get('minimum_order_amount') or None,
                maximum_discount_amount = request.POST.get('maximum_discount_amount') or None,
                usage_limit             = request.POST.get('usage_limit') or None,
                usage_limit_per_customer= request.POST.get('usage_limit_per_customer') or None,
                valid_from              = valid_from,
                valid_until             = valid_until,
                applicable_to_all       = request.POST.get('applicable_to_all') == 'on',
                is_active               = request.POST.get('is_active') == 'on',
            )
            messages.success(request, f'Coupon "{request.POST.get("code", "").upper()}" created successfully!')
            return redirect('adminpanel:coupon_list')

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return render(request, 'adminpanel/promotions/add.html', {'form_data': request.POST})

    return render(request, 'adminpanel/promotions/add.html')


@login_required
@user_passes_test(is_admin)
def coupon_edit(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == 'POST':
        try:
            def parse_dt(val):
                if not val:
                    return None
                dt = parse_datetime(val)
                if dt is None:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        return None
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt

            valid_from  = parse_dt(request.POST.get('valid_from'))
            valid_until = parse_dt(request.POST.get('valid_until'))

            if not valid_from or not valid_until:
                raise ValueError("Please provide both Valid From and Valid Until dates.")
            if valid_until <= valid_from:
                raise ValueError("Valid Until must be after Valid From.")

            discount_type  = request.POST.get('discount_type', coupon.discount_type)
            discount_value = request.POST.get('discount_value') or 0
            if discount_type == 'free_shipping':
                discount_value = 0

            coupon.code                     = request.POST.get('code', '').strip().upper()
            coupon.name                     = request.POST.get('name')
            coupon.description              = request.POST.get('description', '')
            coupon.discount_type            = discount_type
            coupon.discount_value           = discount_value
            coupon.minimum_order_amount     = request.POST.get('minimum_order_amount') or None
            coupon.maximum_discount_amount  = request.POST.get('maximum_discount_amount') or None
            coupon.usage_limit              = request.POST.get('usage_limit') or None
            coupon.usage_limit_per_customer = request.POST.get('usage_limit_per_customer') or None
            coupon.valid_from               = valid_from
            coupon.valid_until              = valid_until
            coupon.applicable_to_all        = request.POST.get('applicable_to_all') == 'on'
            coupon.is_active                = request.POST.get('is_active') == 'on'
            coupon.save()

            messages.success(request, f'Coupon "{coupon.code}" updated!')
            return redirect('adminpanel:coupon_list')

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'adminpanel/promotions/edit.html', {'coupon': coupon})


@login_required
@user_passes_test(is_admin)
def coupon_delete(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Coupon "{code}" deleted.')
        return redirect('adminpanel:coupon_list')
    return redirect('adminpanel:coupon_list')


@login_required
@user_passes_test(is_admin)
def coupon_usage_history(request):
    search = request.GET.get('search', '')
    usage  = CouponUsage.objects.select_related('coupon', 'order', 'user').order_by('-created_at')

    if search:
        usage = usage.filter(
            Q(coupon__code__icontains=search) |
            Q(user__email__icontains=search)  |
            Q(order__order_number__icontains=search)
        )

 
    unique_customers = CouponUsage.objects.values('user').distinct().count()

    total_discount = CouponUsage.objects.aggregate(
        total=Sum('discount_amount')
    )['total'] or Decimal('0.00')

    paginator = Paginator(usage, 25)
    usage     = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/promotions/usage.html', {
        'usage':            usage,
        'search':           search,
        'total_discount':   total_discount,
        'unique_customers': unique_customers,   
    })



from django.views.decorators.http import require_POST

@require_POST
def order_update_tracking(request, order_id):
    """Save tracking number + carrier for an order."""
    order = get_object_or_404(Order, id=order_id)
    order.tracking_number = request.POST.get('tracking_number', '').strip()
    order.carrier         = request.POST.get('carrier', '').strip()
    order.save(update_fields=['tracking_number', 'carrier'])
    messages.success(request, 'Tracking information updated.')
    return redirect('adminpanel:order_detail', order_id)


@require_POST
def order_update_notes(request, order_id):
    """Save internal staff note on an order."""
    order = get_object_or_404(Order, id=order_id)
    order.internal_notes = request.POST.get('internal_notes', '').strip()
    order.save(update_fields=['internal_notes'])
    messages.success(request, 'Internal note saved.')
    return redirect('adminpanel:order_detail', order_id)




# ──────────────────────────────────────────────
#  LIST
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def job_list(request):
    search     = request.GET.get('search', '').strip()
    status     = request.GET.get('status', '')
    job_type   = request.GET.get('job_type', '')
    priority   = request.GET.get('priority', '')
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')

    jobs = JobOrder.objects.select_related('customer', 'assigned_to').order_by('-created_at')

    if search:
        jobs = jobs.filter(
            Q(job_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search) |
            Q(customer_email__icontains=search)
        )
    if status:
        jobs = jobs.filter(status=status)
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    if priority:
        jobs = jobs.filter(priority=priority)
    if date_from:
        jobs = jobs.filter(created_at__date__gte=date_from)
    if date_to:
        jobs = jobs.filter(created_at__date__lte=date_to)

    # Stats for header cards
    total       = JobOrder.objects.count()
    pending     = JobOrder.objects.filter(status__in=['received', 'processing', 'lens_order', 'fitting', 'qa']).count()
    ready       = JobOrder.objects.filter(status='ready').count()
    delivered   = JobOrder.objects.filter(status='delivered').count()
    urgent      = JobOrder.objects.filter(priority='urgent', status__in=['received','processing','lens_order','fitting','qa']).count()

    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'adminpanel/jobs/list.html', {
        'jobs':       jobs_page,
        'search':     search,
        'status':     status,
        'job_type':   job_type,
        'priority':   priority,
        'date_from':  date_from,
        'date_to':    date_to,
        'total':      total,
        'pending':    pending,
        'ready':      ready,
        'delivered':  delivered,
        'urgent':     urgent,
        'status_choices':   JobOrder.STATUS_CHOICES,
        'type_choices':     JobOrder.JOB_TYPE_CHOICES,
        'priority_choices': JobOrder.PRIORITY_CHOICES,
    })


# ──────────────────────────────────────────────
#  ADD
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def job_add(request):
    from users.models import User

    if request.method == 'POST':
        try:
            # Customer info
            customer_id = request.POST.get('customer_id') or None
            customer    = User.objects.get(id=customer_id) if customer_id else None

            job = JobOrder.objects.create(
                job_type        = request.POST.get('job_type', 'in_store'),
                source          = request.POST.get('source', 'walk_in'),
                priority        = request.POST.get('priority', 'normal'),
                customer        = customer,
                customer_name   = request.POST.get('customer_name', ''),
                customer_phone  = request.POST.get('customer_phone', ''),
                customer_email  = request.POST.get('customer_email', ''),

                # Prescription
                re_sphere   = request.POST.get('re_sphere')   or None,
                re_cylinder = request.POST.get('re_cylinder') or None,
                re_axis     = request.POST.get('re_axis')     or None,
                re_add      = request.POST.get('re_add')      or None,
                le_sphere   = request.POST.get('le_sphere')   or None,
                le_cylinder = request.POST.get('le_cylinder') or None,
                le_axis     = request.POST.get('le_axis')     or None,
                le_add      = request.POST.get('le_add')      or None,
                pd_distance = request.POST.get('pd_distance') or None,
                pd_near     = request.POST.get('pd_near')     or None,

                # Products
                frame_description = request.POST.get('frame_description', ''),
                lens_brand        = request.POST.get('lens_brand', ''),
                lens_type         = request.POST.get('lens_type', ''),
                lens_index        = request.POST.get('lens_index', ''),
                lens_coating      = request.POST.get('lens_coating', ''),
                lens_color        = request.POST.get('lens_color', ''),

                # Financials
                frame_price  = request.POST.get('frame_price')  or 0,
                lens_price   = request.POST.get('lens_price')   or 0,
                addon_price  = request.POST.get('addon_price')  or 0,
                discount     = request.POST.get('discount')     or 0,
                total_amount = request.POST.get('total_amount') or 0,
                advance_paid = request.POST.get('advance_paid') or 0,

                promised_date  = request.POST.get('promised_date') or None,
                internal_notes = request.POST.get('internal_notes', ''),
                customer_notes = request.POST.get('customer_notes', ''),
                assigned_to    = User.objects.get(id=request.POST['assigned_to']) if request.POST.get('assigned_to') else None,
                created_by     = request.user,
                prescription_file = request.FILES.get('prescription_file'),
            )

            # Initial history entry
            JobStatusHistory.objects.create(
                job=job, old_status='', new_status='received',
                note='Job created', changed_by=request.user
            )

            messages.success(request, f'Job #{job.job_number} created successfully!')
            return redirect('adminpanel:job_detail', job_id=job.id)

        except Exception as e:
            messages.error(request, f'Error creating job: {str(e)}')

    from users.models import User
    staff_users = User.objects.filter(is_staff=True)
    return render(request, 'adminpanel/jobs/add.html', {
        'status_choices':   JobOrder.STATUS_CHOICES,
        'type_choices':     JobOrder.JOB_TYPE_CHOICES,
        'source_choices':   JobOrder.SOURCE_CHOICES,
        'priority_choices': JobOrder.PRIORITY_CHOICES,
        'staff_users':      staff_users,
    })


# ──────────────────────────────────────────────
#  DETAIL / EDIT
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def job_detail(request, job_id):
    job      = get_object_or_404(JobOrder, id=job_id)
    history  = job.history.select_related('changed_by').order_by('-created_at')
    docs     = job.documents.all()

    return render(request, 'adminpanel/jobs/detail.html', {
        'job':              job,
        'history':          history,
        'docs':             docs,
        'status_choices':   JobOrder.STATUS_CHOICES,
        'priority_choices': JobOrder.PRIORITY_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def job_edit(request, job_id):
    job = get_object_or_404(JobOrder, id=job_id)
    from users.models import User

    if request.method == 'POST':
        try:
            customer_id = request.POST.get('customer_id') or None

            job.job_type        = request.POST.get('job_type', job.job_type)
            job.source          = request.POST.get('source', job.source)
            job.priority        = request.POST.get('priority', job.priority)
            job.customer_name   = request.POST.get('customer_name', job.customer_name)
            job.customer_phone  = request.POST.get('customer_phone', job.customer_phone)
            job.customer_email  = request.POST.get('customer_email', job.customer_email)

            job.re_sphere   = request.POST.get('re_sphere')   or None
            job.re_cylinder = request.POST.get('re_cylinder') or None
            job.re_axis     = request.POST.get('re_axis')     or None
            job.re_add      = request.POST.get('re_add')      or None
            job.le_sphere   = request.POST.get('le_sphere')   or None
            job.le_cylinder = request.POST.get('le_cylinder') or None
            job.le_axis     = request.POST.get('le_axis')     or None
            job.le_add      = request.POST.get('le_add')      or None
            job.pd_distance = request.POST.get('pd_distance') or None
            job.pd_near     = request.POST.get('pd_near')     or None

            job.frame_description = request.POST.get('frame_description', job.frame_description)
            job.lens_brand        = request.POST.get('lens_brand', job.lens_brand)
            job.lens_type         = request.POST.get('lens_type', job.lens_type)
            job.lens_index        = request.POST.get('lens_index', job.lens_index)
            job.lens_coating      = request.POST.get('lens_coating', job.lens_coating)
            job.lens_color        = request.POST.get('lens_color', job.lens_color)

            job.frame_price  = request.POST.get('frame_price')  or 0
            job.lens_price   = request.POST.get('lens_price')   or 0
            job.addon_price  = request.POST.get('addon_price')  or 0
            job.discount     = request.POST.get('discount')     or 0
            job.total_amount = request.POST.get('total_amount') or 0
            job.advance_paid = request.POST.get('advance_paid') or 0

            job.promised_date  = request.POST.get('promised_date') or None
            job.internal_notes = request.POST.get('internal_notes', job.internal_notes)
            job.customer_notes = request.POST.get('customer_notes', job.customer_notes)

            if request.POST.get('assigned_to'):
                job.assigned_to = User.objects.get(id=request.POST['assigned_to'])
            if request.FILES.get('prescription_file'):
                job.prescription_file = request.FILES['prescription_file']

            job.save()
            messages.success(request, f'Job #{job.job_number} updated!')
            return redirect('adminpanel:job_detail', job_id=job.id)

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    staff_users = User.objects.filter(is_staff=True)
    return render(request, 'adminpanel/jobs/edit.html', {
        'job':              job,
        'type_choices':     JobOrder.JOB_TYPE_CHOICES,
        'source_choices':   JobOrder.SOURCE_CHOICES,
        'priority_choices': JobOrder.PRIORITY_CHOICES,
        'staff_users':      staff_users,
    })


# ──────────────────────────────────────────────
#  STATUS UPDATE
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
@require_POST
def job_update_status(request, job_id):
    job        = get_object_or_404(JobOrder, id=job_id)
    new_status = request.POST.get('status')
    note       = request.POST.get('note', '').strip()

    if new_status and new_status != job.status:
        JobStatusHistory.objects.create(
            job=job, old_status=job.status,
            new_status=new_status,
            note=note, changed_by=request.user
        )
        old = job.status
        job.status = new_status
        if new_status == 'delivered':
            job.completed_date = timezone.now()
        job.save()
        messages.success(request, f'Status updated: {old} → {new_status}')
    else:
        messages.warning(request, 'No status change made.')

    return redirect('adminpanel:job_detail', job_id=job.id)


# ──────────────────────────────────────────────
#  DOCUMENT UPLOAD
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
@require_POST
def job_upload_document(request, job_id):
    job = get_object_or_404(JobOrder, id=job_id)
    f   = request.FILES.get('file')
    if f:
        JobDocument.objects.create(
            job=job,
            doc_type    = request.POST.get('doc_type', 'other'),
            file        = f,
            description = request.POST.get('description', ''),
            uploaded_by = request.user,
        )
        messages.success(request, 'Document uploaded.')
    else:
        messages.error(request, 'No file selected.')
    return redirect('adminpanel:job_detail', job_id=job.id)


# ──────────────────────────────────────────────
#  DELETE
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def job_delete(request, job_id):
    job = get_object_or_404(JobOrder, id=job_id)
    if request.method == 'POST':
        num = job.job_number
        job.delete()
        messages.success(request, f'Job #{num} deleted.')
        return redirect('adminpanel:job_list')
    return render(request, 'adminpanel/jobs/delete_confirm.html', {'job': job})


# ──────────────────────────────────────────────
#  AJAX: Customer search autocomplete
# ──────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def job_customer_search(request):
    q = request.GET.get('q', '').strip()
    from users.models import User
    if len(q) >= 2:
        users = User.objects.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(email__icontains=q)      |
            Q(phone__icontains=q)
        )[:10]
        data = [{'id': u.id, 'name': u.get_full_name() or u.email,
                 'email': u.email,
                 'phone': getattr(u, 'phone', '')} for u in users]
    else:
        data = []
    return JsonResponse({'results': data})



@login_required
@user_passes_test(is_admin)
def kids_list(request):
    search = request.GET.get('search', '')
    brand_id = request.GET.get('brand', '')
    stock_status = request.GET.get('stock_status', '')

    products = Product.objects.select_related('brand', 'category').filter(
        age_group='kids'
    ).order_by('-created_at')

    total_count = products.count()
    low_stock_count = products.filter(track_inventory=True, stock_quantity__lte=5, stock_quantity__gt=0).count()
    out_of_stock_count = products.filter(track_inventory=True, stock_quantity=0).count()

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
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
        'brands': Brand.objects.filter(available_for_kids=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'search': search,
        'current_brand': brand_id,
        'stock_status': stock_status,
        'total_count': total_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'product_type_label': 'Kids',
        'add_url': 'adminpanel:kids_add',
    }
    return render(request, 'adminpanel/kids/list.html', context)


@login_required
@user_passes_test(is_admin)
def kids_add(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                product = Product.objects.create(
                    name=request.POST.get('name'),
                    sku=request.POST.get('sku'),
                    slug=request.POST.get('slug'),
                    product_type=request.POST.get('product_type', 'eyeglasses'),
                    category_id=request.POST.get('category'),
                    brand_id=request.POST.get('brand') or None,
                    short_description=request.POST.get('short_description', ''),
                    description=request.POST.get('description', ''),
                    gender=request.POST.get('gender', 'unisex'),
                    age_group='kids',
                    base_price=request.POST.get('base_price'),
                    compare_at_price=request.POST.get('compare_at_price') or None,
                    track_inventory=request.POST.get('track_inventory') == 'on',
                    stock_quantity=int(request.POST.get('stock_quantity') or 0),
                    is_active=request.POST.get('is_active') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                )
                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx == 0))

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

                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')
                for key, val in zip(s_keys, s_values):
                    if key.strip():
                        ProductSpecification.objects.create(product=product, spec_key=key, spec_value=val)

                messages.success(request, 'Kids product added!')
                return redirect('adminpanel:kids_list')
        except IntegrityError:
            messages.error(request, 'SKU or Slug already exists.')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'brands': Brand.objects.filter(available_for_kids=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'product_types': [('eyeglasses', 'Eyeglasses'), ('sunglasses', 'Sunglasses')],
        'section_label': 'Kids',
        'list_url': 'adminpanel:kids_list',
    }
    return render(request, 'adminpanel/kids/add.html', context)


@login_required
@user_passes_test(is_admin)
def kids_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id, age_group='kids')
    if request.method == 'POST':
        try:
            with transaction.atomic():
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.product_type = request.POST.get('product_type')
                product.category_id = request.POST.get('category')
                product.brand_id = request.POST.get('brand') or None
                product.short_description = request.POST.get('short_description', '')
                product.description = request.POST.get('description', '')
                product.gender = request.POST.get('gender', 'unisex')
                product.base_price = request.POST.get('base_price')
                product.compare_at_price = request.POST.get('compare_at_price') or None
                product.track_inventory = request.POST.get('track_inventory') == 'on'
                product.stock_quantity = int(request.POST.get('stock_quantity') or 0)
                product.is_active = request.POST.get('is_active') == 'on'
                product.is_featured = request.POST.get('is_featured') == 'on'
                product.save()

                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)
                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()

                v_ids = request.POST.getlist('variant_id[]')
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_sizes = request.POST.getlist('variant_size[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')
                kept_ids = []
                for i, sku in enumerate(v_skus):
                    if not sku.strip():
                        continue
                    vid = v_ids[i] if i < len(v_ids) else None
                    if vid and vid != '0':
                        v = ProductVariant.objects.get(id=vid)
                        v.variant_sku = sku; v.color_name = v_colors[i]
                        v.size = v_sizes[i]; v.price_adjustment = v_prices[i] or 0
                        v.stock_quantity = v_stocks[i] or 0; v.save()
                        kept_ids.append(v.id)
                    else:
                        v = ProductVariant.objects.create(
                            product=product, variant_sku=sku, color_name=v_colors[i],
                            size=v_sizes[i], price_adjustment=v_prices[i] or 0, stock_quantity=v_stocks[i] or 0
                        )
                        kept_ids.append(v.id)
                product.variants.exclude(id__in=kept_ids).delete()

                messages.success(request, 'Kids product updated!')
                return redirect('adminpanel:kids_list')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'product': product,
        'brands': Brand.objects.filter(available_for_kids=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'product_types': [('eyeglasses', 'Eyeglasses'), ('sunglasses', 'Sunglasses')],
        'images': product.images.all(),
        'variants': product.variants.all(),
        'specifications': product.specifications.all(),
        'section_label': 'Kids',
        'list_url': 'adminpanel:kids_list',
    }
    return render(request, 'adminpanel/kids/edit.html', context)


@login_required
@user_passes_test(is_admin)
def kids_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id, age_group='kids')
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Kids product deleted.')
        return redirect('adminpanel:kids_list')
    return render(request, 'adminpanel/kids/delete_confirm.html', {'product': product})


# ==================== ACCESSORIES ====================

@login_required
@user_passes_test(is_admin)
def accessories_list(request):
    search = request.GET.get('search', '')
    brand_id = request.GET.get('brand', '')
    stock_status = request.GET.get('stock_status', '')

    products = Product.objects.select_related('brand', 'category').filter(
        product_type='accessories'
    ).order_by('-created_at')

    total_count = products.count()
    low_stock_count = products.filter(track_inventory=True, stock_quantity__lte=5, stock_quantity__gt=0).count()
    out_of_stock_count = products.filter(track_inventory=True, stock_quantity=0).count()

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
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
        'brands': Brand.objects.filter(available_for_accessories=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'search': search,
        'current_brand': brand_id,
        'stock_status': stock_status,
        'total_count': total_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'adminpanel/accessories/list.html', context)


@login_required
@user_passes_test(is_admin)
def accessories_add(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                product = Product.objects.create(
                    name=request.POST.get('name'),
                    sku=request.POST.get('sku'),
                    slug=request.POST.get('slug'),
                    product_type='accessories',
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
                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx == 0))

                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')
                for key, val in zip(s_keys, s_values):
                    if key.strip():
                        ProductSpecification.objects.create(product=product, spec_key=key, spec_value=val)

                messages.success(request, 'Accessory added!')
                return redirect('adminpanel:accessories_list')
        except IntegrityError:
            messages.error(request, 'SKU or Slug already exists.')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'brands': Brand.objects.filter(available_for_accessories=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
    }
    return render(request, 'adminpanel/accessories/add.html', context)


@login_required
@user_passes_test(is_admin)
def accessories_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id, product_type='accessories')
    if request.method == 'POST':
        try:
            with transaction.atomic():
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
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

                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)
                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()

                messages.success(request, 'Accessory updated!')
                return redirect('adminpanel:accessories_list')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'product': product,
        'brands': Brand.objects.filter(available_for_accessories=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'images': product.images.all(),
        'specifications': product.specifications.all(),
    }
    return render(request, 'adminpanel/accessories/edit.html', context)


@login_required
@user_passes_test(is_admin)
def accessories_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id, product_type='accessories')
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Accessory deleted.')
        return redirect('adminpanel:accessories_list')
    return render(request, 'adminpanel/accessories/delete_confirm.html', {'product': product})


# ==================== READING GLASSES ====================

@login_required
@user_passes_test(is_admin)
def reading_glasses_list(request):
    search = request.GET.get('search', '')
    brand_id = request.GET.get('brand', '')
    stock_status = request.GET.get('stock_status', '')

    products = Product.objects.select_related('brand', 'category').filter(
        product_type='reading_glasses'
    ).order_by('-created_at')

    total_count = products.count()
    low_stock_count = products.filter(track_inventory=True, stock_quantity__lte=5, stock_quantity__gt=0).count()
    out_of_stock_count = products.filter(track_inventory=True, stock_quantity=0).count()

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
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
        'brands': Brand.objects.filter(available_for_reading_glasses=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'search': search,
        'current_brand': brand_id,
        'stock_status': stock_status,
        'total_count': total_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'adminpanel/reading_glasses/list.html', context)


@login_required
@user_passes_test(is_admin)
def reading_glasses_add(request):
    # Reading glasses have power options (e.g. +1.00, +1.50 ... +3.50)
    READING_POWERS = ['+1.00', '+1.25', '+1.50', '+1.75', '+2.00', '+2.25', '+2.50', '+2.75', '+3.00', '+3.25', '+3.50']

    if request.method == 'POST':
        try:
            with transaction.atomic():
                product = Product.objects.create(
                    name=request.POST.get('name'),
                    sku=request.POST.get('sku'),
                    slug=request.POST.get('slug'),
                    product_type='reading_glasses',
                    category_id=request.POST.get('category'),
                    brand_id=request.POST.get('brand') or None,
                    short_description=request.POST.get('short_description', ''),
                    description=request.POST.get('description', ''),
                    gender=request.POST.get('gender', 'unisex'),
                    age_group='adult',
                    base_price=request.POST.get('base_price'),
                    compare_at_price=request.POST.get('compare_at_price') or None,
                    track_inventory=request.POST.get('track_inventory') == 'on',
                    stock_quantity=int(request.POST.get('stock_quantity') or 0),
                    is_active=request.POST.get('is_active') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                )
                for idx, img in enumerate(request.FILES.getlist('images')):
                    ProductImage.objects.create(product=product, image=img, is_primary=(idx == 0))

                # Save color variants
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')
                for sku, color, price, stock in zip(v_skus, v_colors, v_prices, v_stocks):
                    if sku.strip():
                        ProductVariant.objects.create(
                            product=product, variant_sku=sku, color_name=color,
                            price_adjustment=price or 0, stock_quantity=stock or 0
                        )

                s_keys = request.POST.getlist('spec_key[]')
                s_values = request.POST.getlist('spec_value[]')
                for key, val in zip(s_keys, s_values):
                    if key.strip():
                        ProductSpecification.objects.create(product=product, spec_key=key, spec_value=val)

                messages.success(request, 'Reading glasses added!')
                return redirect('adminpanel:reading_glasses_list')
        except IntegrityError:
            messages.error(request, 'SKU or Slug already exists.')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'brands': Brand.objects.filter(available_for_reading_glasses=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'reading_powers': READING_POWERS,
    }
    return render(request, 'adminpanel/reading_glasses/add.html', context)


@login_required
@user_passes_test(is_admin)
def reading_glasses_edit(request, product_id):
    READING_POWERS = ['+1.00', '+1.25', '+1.50', '+1.75', '+2.00', '+2.25', '+2.50', '+2.75', '+3.00', '+3.25', '+3.50']
    product = get_object_or_404(Product, id=product_id, product_type='reading_glasses')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                product.name = request.POST.get('name')
                product.sku = request.POST.get('sku')
                product.slug = request.POST.get('slug')
                product.category_id = request.POST.get('category')
                product.brand_id = request.POST.get('brand') or None
                product.short_description = request.POST.get('short_description', '')
                product.description = request.POST.get('description', '')
                product.gender = request.POST.get('gender', 'unisex')
                product.base_price = request.POST.get('base_price')
                product.compare_at_price = request.POST.get('compare_at_price') or None
                product.track_inventory = request.POST.get('track_inventory') == 'on'
                product.stock_quantity = int(request.POST.get('stock_quantity') or 0)
                product.is_active = request.POST.get('is_active') == 'on'
                product.is_featured = request.POST.get('is_featured') == 'on'
                product.save()

                for img in request.FILES.getlist('images'):
                    ProductImage.objects.create(product=product, image=img)
                del_ids = request.POST.get('delete_image_ids', '')
                if del_ids:
                    ProductImage.objects.filter(id__in=[int(i) for i in del_ids.split(',') if i.isdigit()]).delete()

                v_ids = request.POST.getlist('variant_id[]')
                v_skus = request.POST.getlist('variant_sku[]')
                v_colors = request.POST.getlist('variant_color[]')
                v_prices = request.POST.getlist('variant_price[]')
                v_stocks = request.POST.getlist('variant_stock[]')
                kept_ids = []
                for i, sku in enumerate(v_skus):
                    if not sku.strip():
                        continue
                    vid = v_ids[i] if i < len(v_ids) else None
                    if vid and vid != '0':
                        v = ProductVariant.objects.get(id=vid)
                        v.variant_sku = sku; v.color_name = v_colors[i]
                        v.price_adjustment = v_prices[i] or 0; v.stock_quantity = v_stocks[i] or 0
                        v.save(); kept_ids.append(v.id)
                    else:
                        v = ProductVariant.objects.create(
                            product=product, variant_sku=sku, color_name=v_colors[i],
                            price_adjustment=v_prices[i] or 0, stock_quantity=v_stocks[i] or 0
                        )
                        kept_ids.append(v.id)
                product.variants.exclude(id__in=kept_ids).delete()

                messages.success(request, 'Reading glasses updated!')
                return redirect('adminpanel:reading_glasses_list')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'product': product,
        'brands': Brand.objects.filter(available_for_reading_glasses=True, is_active=True),
        'categories': Category.objects.filter(is_active=True),
        'images': product.images.all(),
        'variants': product.variants.all(),
        'specifications': product.specifications.all(),
        'reading_powers': READING_POWERS,
    }
    return render(request, 'adminpanel/reading_glasses/edit.html', context)


@login_required
@user_passes_test(is_admin)
def reading_glasses_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id, product_type='reading_glasses')
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Reading glasses deleted.')
        return redirect('adminpanel:reading_glasses_list')
    return render(request, 'adminpanel/reading_glasses/delete_confirm.html', {'product': product})
