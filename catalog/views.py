from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.db.models import Q, Min, Max
from django.contrib.auth.decorators import login_required
from .models import (
    Product, Category, Brand, ProductVariant, 
    ContactLensProduct, ContactLensColor, LensBrand, 
    LensType, LensOption
)
from django.utils import timezone
from content.models import Banner
from django.db import models as db_models

# Home Page
def home_view(request):
    now = timezone.now()

    hero_slides = Banner.objects.filter(
        banner_type='homepage', placement='main_slider', is_active=True,
    ).filter(
        db_models.Q(start_date__isnull=True) | db_models.Q(start_date__lte=now)
    ).filter(
        db_models.Q(end_date__isnull=True) | db_models.Q(end_date__gte=now)
    ).order_by('display_order')

    featured_products   = Product.objects.filter(is_featured=True, is_active=True).select_related('brand').prefetch_related('images')[:8]
    new_arrivals        = Product.objects.filter(is_active=True).select_related('brand').prefetch_related('images').order_by('-created_at')[:8]
    eyeglasses_preview  = Product.objects.filter(product_type='eyeglasses', is_active=True).select_related('brand').prefetch_related('images', 'variants')[:3]
    top_brands          = Brand.objects.filter(is_active=True).order_by('display_order')[:3]
    brands              = Brand.objects.filter(is_active=True).order_by('display_order')[:12]

    return render(request, 'home.html', {
        'hero_slides':        hero_slides,
        'featured_products':  featured_products,
        'new_arrivals':       new_arrivals,
        'eyeglasses_preview': eyeglasses_preview,
        'top_brands':         top_brands,
        'brands':             brands,
    })


# Product List Views
class ProductListView(ListView):
    """Generic product listing view"""
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'
    paginate_by = 24

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related('brand', 'category')
        
        # Filter by product type
        product_type = self.kwargs.get('product_type')
        if product_type:
            queryset = queryset.filter(product_type=product_type)
        
        # Filter by category
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by brand
        brand_slug = self.request.GET.get('brand')
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        
        # Filter by gender
        gender = self.request.GET.get('gender')
        if gender and gender != 'all':
            queryset = queryset.filter(gender=gender)
        
        # Filter by price range
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)
        
        # Search query
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(brand__name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Sorting
        sort = self.request.GET.get('sort', '-created_at')
        queryset = queryset.order_by(sort)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_type = self.kwargs.get('product_type')
        
        # Get filter options
        context['brands'] = Brand.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)
        context['product_type'] = product_type
        context['selected_gender'] = self.request.GET.get('gender', 'all')
        
        # Price range
        price_range = Product.objects.filter(is_active=True).aggregate(
            min_price=Min('base_price'),
            max_price=Max('base_price')
        )
        context['price_range'] = price_range
        
        return context

# Sunglasses
from django.core.paginator import Paginator

def sunglasses_list(request):
    """Sunglasses listing page with advanced filtering"""
    queryset = Product.objects.filter(
        product_type='sunglasses', 
        is_active=True
    ).select_related('brand', 'category')
    
    # 1. Gender Filter
    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        queryset = queryset.filter(gender=gender)
    
    # 2. Brand Filter (Handle Multiple Checkboxes)
    # request.GET.getlist('brand') captures ?brand=ray-ban&brand=gucci
    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)
    
    # 3. Price Filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)
        
    # 4. Sorting
    sort_option = request.GET.get('sort', '-created_at')
    # Validate sort option to prevent errors
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name']
    if sort_option in valid_sorts:
        queryset = queryset.order_by(sort_option)
    else:
        queryset = queryset.order_by('-created_at')

    # 5. Pagination
    paginator = Paginator(queryset, 24) # Show 24 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj, # Pass page_obj, not full queryset
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'brands': Brand.objects.filter(available_for_sunglasses=True, is_active=True),
        # Pass selections back to template to keep boxes checked
        'selected_gender': gender,
        'selected_brands': selected_brands,
        'current_sort': sort_option,
    }
    return render(request, 'sunglasses_list.html', context)


# Eyeglasses
def eyeglasses_list(request):
    """Eyeglasses listing page"""
    products = Product.objects.filter(
        product_type='eyeglasses', 
        is_active=True
    ).select_related('brand', 'category')
    
    # Filters
    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        products = products.filter(gender=gender)
    
    brand_slug = request.GET.get('brand')
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    
    context = {
        'products': products,
        'brands': Brand.objects.filter(available_for_eyeglasses=True, is_active=True),
        'selected_gender': gender,
    }
    return render(request, 'eyeglasses_list.html', context)


# Contact Lenses
def contact_lenses_list(request):
    """Contact lenses listing page"""
    products = Product.objects.filter(
        product_type='contact_lenses', 
        is_active=True
    ).select_related('brand', 'contact_lens')
    
    # Filter by lens type (clear/color)
    lens_type = request.GET.get('lens_type')
    if lens_type:
        products = products.filter(contact_lens__lens_type=lens_type)
    
    # Filter by replacement schedule
    schedule = request.GET.get('schedule')
    if schedule:
        products = products.filter(contact_lens__replacement_schedule=schedule)
    
    brand_slug = request.GET.get('brand')
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    
    context = {
        'products': products,
        'brands': Brand.objects.filter(available_for_contact_lenses=True, is_active=True),
        'selected_lens_type': lens_type,
        'selected_schedule': schedule,
    }
    return render(request, 'contact_lenses_list.html', context)


# Product Detail Views
# class ProductDetailView(DetailView):
#     """Product detail page"""
#     model = Product
#     template_name = 'product_detail.html'
#     context_object_name = 'product'
#     slug_field = 'slug'

#     def get_queryset(self):
#         return Product.objects.filter(is_active=True).select_related(
#             'brand', 'category'
#         ).prefetch_related(
#             'variants', 'images', 'specifications'
#         )

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         product = self.object
        
#         # Get variants
#         context['variants'] = product.variants.filter(is_active=True)
        
#         # Get default variant
#         context['default_variant'] = product.variants.filter(
#             is_default=True, is_active=True
#         ).first()
        
#         # Get images
#         context['images'] = product.images.all()
        
#         # Get specifications
#         context['specifications'] = product.specifications.all()
        
#         # Related products
#         context['related_products'] = Product.objects.filter(
#             category=product.category,
#             is_active=True
#         ).exclude(id=product.id)[:4]
        
#         # For contact lenses, get color options
#         if product.product_type == 'contact_lenses':
#             try:
#                 contact_lens = product.contact_lens
#                 context['contact_lens'] = contact_lens
#                 context['colors'] = contact_lens.colors.filter(is_active=True)
#             except ContactLensProduct.DoesNotExist:
#                 pass
        
#         return context

def accessory_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug, product_type='accessories', is_active=True
    )
    all_images = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images = all_images.exclude(id=primary_image.id) if primary_image else all_images

    context = {
        'product': product,
        'primary_image': primary_image,
        'images': extra_images,
        'variants': product.variants.filter(is_active=True),
        'specifications': product.specifications.all(),
        'related_products': Product.objects.filter(
            category=product.category, product_type='accessories', is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    return render(request, 'accessory_detail.html', context)


# Sunglass Detail
def sunglass_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug,
        product_type='sunglasses',
        is_active=True
    )

    all_images = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images = all_images.exclude(id=primary_image.id) if primary_image else all_images

    context = {
        'product': product,
        'primary_image': primary_image,         
        'images': extra_images,                  
        'variants': product.variants.filter(is_active=True),
        'specifications': product.specifications.all(),
        'related_products': Product.objects.filter(
            category=product.category,
            product_type='sunglasses',
            is_active=True
        ).exclude(id=product.id)[:4]
    }
    return render(request, 'sunglass_detail.html', context)


# Eyeglass Detail
def eyeglass_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug, product_type='eyeglasses', is_active=True
    )
    all_images = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images = all_images.exclude(id=primary_image.id) if primary_image else all_images

    lens_brands = LensBrand.objects.filter(is_active=True)
    lens_types = LensType.objects.filter(is_active=True)

    context = {
        'product': product,
        'primary_image': primary_image,
        'images': extra_images,
        'variants': product.variants.filter(is_active=True),
        'specifications': product.specifications.all(),
        'lens_brands': lens_brands,
        'lens_types': lens_types,
        'related_products': Product.objects.filter(
            category=product.category, product_type='eyeglasses', is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    return render(request, 'eyeglass_detail.html', context)



# Contact Lens Detail
def contact_lens_detail(request, slug):
    """Contact lens product detail page"""
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'contact_lens'),
        slug=slug,
        product_type='contact_lenses',
        is_active=True
    )
    
    contact_lens = product.contact_lens
    colors = contact_lens.colors.filter(is_active=True)
    
    # Power ranges for color lenses
    power_ranges = [
        -1.00, -1.25, -1.50, -1.75, -2.00, -2.25, -2.50, 
        -2.75, -3.00, -3.25, -3.50, -3.75, -4.00
    ]
    
    context = {
        'product': product,
        'contact_lens': contact_lens,
        'colors': colors,
        'power_ranges': power_ranges,
        'images': product.images.all(),
        'related_products': Product.objects.filter(
            product_type='contact_lenses',
            is_active=True
        ).exclude(id=product.id)[:4]
    }
    return render(request, 'contact_lens_detail.html', context)


# Brand Pages
def brand_list(request):
    """All brands listing page"""
    brands = Brand.objects.filter(is_active=True).order_by('display_order', 'name')
    
    context = {
        'brands': brands,
    }
    return render(request, 'brand_list.html', context)


def brand_detail(request, slug):
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    products = Product.objects.filter(brand=brand, is_active=True)

    product_type = request.GET.get('type')
    if product_type:
        products = products.filter(product_type=product_type)

    sort = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    if sort in valid_sorts:
        products = products.order_by(sort)

    context = {
        'brand': brand,
        'products': products.select_related('brand', 'category').prefetch_related('images', 'variants'),
        'other_brands': Brand.objects.filter(is_active=True).exclude(id=brand.id).order_by('display_order')[:10],
    }
    return render(request, 'brand_detail.html', context)


# Category Pages
def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True).select_related('brand').prefetch_related('images', 'variants')
    
    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        products = products.filter(gender=gender)
    
    sort = request.GET.get('sort', '-created_at')
    valid = ['-created_at','base_price','-base_price','name','-name']
    products = products.order_by(sort if sort in valid else '-created_at')
    
    paginator = Paginator(products, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'category_detail.html', {
        'category': category,
        'products': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'selected_gender': gender,
    })


# Search
def search_view(request):
    """Search functionality"""
    query = request.GET.get('q', '')
    products = Product.objects.none()
    
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query),
            is_active=True
        ).select_related('brand', 'category').distinct()
    
    context = {
        'query': query,
        'products': products,
        'count': products.count(),
    }
    return render(request, 'search_results.html', context)


# API-like views for AJAX requests
def get_lens_options(request):
    """Get lens options based on lens type"""
    from django.http import JsonResponse
    
    lens_type_id = request.GET.get('lens_type_id')
    lens_brand_id = request.GET.get('lens_brand_id')
    
    lens_options = LensOption.objects.filter(
        lens_type_id=lens_type_id,
        lens_brand_id=lens_brand_id
    ).values('id', 'index', 'base_price', 'min_power', 'max_power')
    
    return JsonResponse(list(lens_options), safe=False)


def get_contact_lens_powers(request):
    """Get available powers for a contact lens color"""
    from django.http import JsonResponse
    
    color_id = request.GET.get('color_id')
    
    try:
        color = ContactLensColor.objects.get(id=color_id)
        if color.power_enabled:
            powers = color.power_options.filter(is_available=True).values(
                'power_value', 'stock_quantity'
            )
            return JsonResponse({
                'power_enabled': True,
                'powers': list(powers)
            })
        else:
            return JsonResponse({
                'power_enabled': False,
                'message': 'Power not available for this color'
            })
    except ContactLensColor.DoesNotExist:
        return JsonResponse({'error': 'Color not found'}, status=404)
    


# ── Medical Lens Views ─────────────────────────────────────────────────────────
# Add these to your catalog/views.py

from django.db.models import Min, Max, Q
from django.core.paginator import Paginator

def medical_lenses_list(request):
    """
    Medical lenses listing page.
    Filters by: lens_brand, lens_type, index, coating, price.
    Per PDF checklist: lens brands, coatings, and index options.
    """
    # Base queryset — LensOption is the medical lens product model
    queryset = LensOption.objects.filter(is_active=True).select_related(
        'lens_brand', 'lens_type'
    ).prefetch_related('coatings')

    # 1. Lens Brand filter
    selected_lens_brands = request.GET.getlist('lens_brand')
    if selected_lens_brands:
        queryset = queryset.filter(lens_brand__slug__in=selected_lens_brands)

    # 2. Lens Type filter (Single Vision, Progressive, Bifocal, etc.)
    selected_lens_types = request.GET.getlist('lens_type')
    if selected_lens_types:
        queryset = queryset.filter(lens_type__slug__in=selected_lens_types)

    # 3. Index filter (1.50, 1.56, 1.60, 1.67, 1.74 etc.)
    selected_indexes = request.GET.getlist('index')
    if selected_indexes:
        queryset = queryset.filter(index__in=selected_indexes)

    # 4. Coating filter
    selected_coatings = request.GET.getlist('coating')
    if selected_coatings:
        queryset = queryset.filter(coatings__code__in=selected_coatings).distinct()

    # 5. Price filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    # 6. Sorting
    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    # 7. Pagination
    paginator = Paginator(queryset, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Price range for slider
    price_range = LensOption.objects.filter(is_active=True).aggregate(
        min_price=Min('base_price'),
        max_price=Max('base_price')
    )

    # Common index values to display in sidebar filter
    index_options = (
        LensOption.objects
        .filter(is_active=True)
        .values_list('index', flat=True)
        .distinct()
        .order_by('index')
    )

    context = {
        'lens_options':          page_obj,
        'page_obj':              page_obj,
        'is_paginated':          page_obj.has_other_pages(),
        'lens_brands':           LensBrand.objects.filter(is_active=True).order_by('name'),
        'lens_types':            LensType.objects.filter(is_active=True).order_by('name'),
        'index_options':         index_options,
        'price_range':           price_range,
        # Pass back selections to keep sidebar checked
        'selected_lens_brands':  selected_lens_brands,
        'selected_lens_types':   selected_lens_types,
        'selected_indexes':      selected_indexes,
        'selected_coatings':     selected_coatings,
        'current_sort':          sort_option,
    }
    return render(request, 'medical_lenses_list.html', context)


def medical_lens_detail(request, pk):
    """
    Medical lens (LensOption) detail page.
    Shows index, brand, coating, power range, and prescription entry.
    """
    lens_option = get_object_or_404(
        LensOption.objects.select_related('lens_brand', 'lens_type')
                          .prefetch_related('coatings'),
        pk=pk,
        is_active=True
    )

    # Related lenses: same lens_type, exclude self, limit 4
    related_lens_options = (
        LensOption.objects
        .filter(is_active=True)
        .exclude(pk=pk)
        .select_related('lens_brand', 'lens_type')
    )
    # Prefer same lens type first
    if lens_option.lens_type:
        related_same_type = related_lens_options.filter(
            lens_type=lens_option.lens_type
        )[:4]
        if related_same_type.count() < 4:
            # backfill from other types
            excluded_ids = list(related_same_type.values_list('id', flat=True)) + [pk]
            extra = related_lens_options.exclude(id__in=excluded_ids)[:4 - related_same_type.count()]
            from itertools import chain
            related_lens_options = list(chain(related_same_type, extra))
        else:
            related_lens_options = related_same_type
    else:
        related_lens_options = related_lens_options[:4]

    context = {
        'lens_option':         lens_option,
        'related_lens_options': related_lens_options,
    }
    return render(request, 'medical_lens_detail.html', context)