from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.db.models import Q, Min, Max
from django.contrib.auth.decorators import login_required
from reviews.reviews_context import get_review_context
from cart import models
from .models import (
    Product, Category, Brand, ProductVariant,
    ContactLensProduct, ContactLensColor, LensBrand,
    LensType, LensOption
)
from django.utils import timezone
from content.models import Banner
from django.core.paginator import Paginator
from django.db import models as db_models


# ── Home Page ─────────────────────────────────────────────────────────────────
def home_view(request):
    now = timezone.now()

    hero_slides = Banner.objects.filter(
        placement='main_slider',
        is_active=True,
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=now)
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    ).order_by('display_order')

    sale_banner = Banner.objects.filter(
        placement='sale_banner',
        is_active=True,
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=now)
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    ).order_by('display_order').first()

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
        'sale_banner':        sale_banner,
    })


# ── Generic Product List View ──────────────────────────────────────────────────
class ProductListView(ListView):
    """Generic product listing view"""
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'
    paginate_by = 24

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related('brand', 'category')

        product_type = self.kwargs.get('product_type')
        if product_type:
            queryset = queryset.filter(product_type=product_type)

        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        brand_slug = self.request.GET.get('brand')
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)

        gender = self.request.GET.get('gender')
        if gender and gender != 'all':
            queryset = queryset.filter(gender=gender)

        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(brand__name__icontains=search) |
                Q(description__icontains=search)
            )

        sort = self.request.GET.get('sort', '-created_at')
        queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_type = self.kwargs.get('product_type')

        context['brands'] = Brand.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)
        context['product_type'] = product_type
        context['selected_gender'] = self.request.GET.get('gender', 'all')

        price_range = Product.objects.filter(is_active=True).aggregate(
            min_price=Min('base_price'),
            max_price=Max('base_price')
        )
        context['price_range'] = price_range

        return context


# ── Sunglasses List ────────────────────────────────────────────────────────────
def sunglasses_list(request):
    """Sunglasses listing page with advanced filtering"""
    queryset = Product.objects.filter(
        product_type='sunglasses',
        is_active=True
    ).select_related('brand', 'category')

    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        queryset = queryset.filter(gender=gender)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'products':        page_obj,
        'is_paginated':    page_obj.has_other_pages(),
        'page_obj':        page_obj,
        'brands':          Brand.objects.filter(available_for_sunglasses=True, is_active=True),
        'selected_gender': gender,
        'selected_brands': selected_brands,
        'current_sort':    sort_option,
    }
    return render(request, 'sunglasses_list.html', context)


# ── Eyeglasses List ────────────────────────────────────────────────────────────
def eyeglasses_list(request):
    """Eyeglasses listing page"""
    queryset = Product.objects.filter(
        product_type='eyeglasses',
        is_active=True
    ).select_related('brand', 'category')

    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        queryset = queryset.filter(gender=gender)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    price_range = Product.objects.filter(
        product_type='eyeglasses', is_active=True
    ).aggregate(min_price=Min('base_price'), max_price=Max('base_price'))

    context = {
        'products':        page_obj,
        'is_paginated':    page_obj.has_other_pages(),
        'page_obj':        page_obj,
        'brands':          Brand.objects.filter(available_for_eyeglasses=True, is_active=True),
        'price_range':     price_range,
        'selected_gender': gender,
        'selected_brands': selected_brands,
        'current_sort':    sort_option,
    }
    return render(request, 'eyeglasses_list.html', context)


# ── Contact Lenses List ────────────────────────────────────────────────────────
def contact_lenses_list(request):
    """Contact lenses listing page"""
    queryset = Product.objects.filter(
        product_type='contact_lenses',
        is_active=True
    ).select_related('brand', 'contact_lens')

    lens_type = request.GET.get('lens_type')
    if lens_type:
        queryset = queryset.filter(contact_lens__lens_type=lens_type)

    schedule = request.GET.get('schedule')
    if schedule:
        queryset = queryset.filter(contact_lens__replacement_schedule=schedule)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    price_range = Product.objects.filter(
        product_type='contact_lenses', is_active=True
    ).aggregate(min_price=Min('base_price'), max_price=Max('base_price'))

    context = {
        'products':          page_obj,
        'is_paginated':      page_obj.has_other_pages(),
        'page_obj':          page_obj,
        'brands':            Brand.objects.filter(available_for_contact_lenses=True, is_active=True),
        'price_range':       price_range,
        'selected_lens_type': lens_type,
        'selected_schedule': schedule,
        'selected_brands':   selected_brands,
        'current_sort':      sort_option,
    }
    return render(request, 'contact_lenses_list.html', context)


# ── Sunglass Detail ────────────────────────────────────────────────────────────
def sunglass_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug,
        product_type='sunglasses',
        is_active=True
    )

    all_images    = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images  = all_images.exclude(id=primary_image.id) if primary_image else all_images

    context = {
        'product':          product,
        'primary_image':    primary_image,
        'images':           extra_images,
        'variants':         product.variants.filter(is_active=True),
        'specifications':   product.specifications.all(),
        'related_products': Product.objects.filter(
            category=product.category,
            product_type='sunglasses',
            is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    context.update(get_review_context(request, product))
    return render(request, 'sunglass_detail.html', context)


# ── Eyeglass Detail ────────────────────────────────────────────────────────────
def eyeglass_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug, product_type='eyeglasses', is_active=True
    )
    all_images    = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images  = all_images.exclude(id=primary_image.id) if primary_image else all_images

    lens_brands = LensBrand.objects.filter(is_active=True)
    lens_types  = LensType.objects.filter(is_active=True)

    context = {
        'product':          product,
        'primary_image':    primary_image,
        'images':           extra_images,
        'variants':         product.variants.filter(is_active=True),
        'specifications':   product.specifications.all(),
        'lens_brands':      lens_brands,
        'lens_types':       lens_types,
        'related_products': Product.objects.filter(
            category=product.category, product_type='eyeglasses', is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    context.update(get_review_context(request, product))
    return render(request, 'eyeglass_detail.html', context)


# ── Contact Lens Detail ────────────────────────────────────────────────────────
def contact_lens_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'contact_lens'),
        slug=slug, product_type='contact_lenses', is_active=True
    )
    contact_lens = product.contact_lens
    colors       = contact_lens.colors.filter(is_active=True)

    all_images    = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images  = all_images.exclude(id=primary_image.id) if primary_image else all_images

    power_ranges = [
        -1.00, -1.25, -1.50, -1.75, -2.00, -2.25, -2.50,
        -2.75, -3.00, -3.25, -3.50, -3.75, -4.00
    ]

    context = {
        'product':          product,
        'primary_image':    primary_image,
        'images':           extra_images,
        'contact_lens':     contact_lens,
        'colors':           colors,
        'power_ranges':     power_ranges,
        'related_products': Product.objects.filter(
            product_type='contact_lenses', is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    context.update(get_review_context(request, product))
    return render(request, 'contact_lens_detail.html', context)


# ── Accessory Detail ───────────────────────────────────────────────────────────
def accessory_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug, product_type='accessories', is_active=True
    )
    all_images    = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images  = all_images.exclude(id=primary_image.id) if primary_image else all_images

    context = {
        'product':          product,
        'primary_image':    primary_image,
        'images':           extra_images,
        'variants':         product.variants.filter(is_active=True),
        'specifications':   product.specifications.all(),
        'related_products': Product.objects.filter(
            category=product.category, product_type='accessories', is_active=True
        ).exclude(id=product.id).prefetch_related('images')[:4]
    }
    context.update(get_review_context(request, product))
    return render(request, 'accessory_detail.html', context)


# ── Kids Detail ───────────────────────────────────────────────────────────────
def kids_detail(request, slug):
    """
    Kids product detail page.
    Supports both eyeglasses and sunglasses with gender='kids'.
    - Eyeglasses: mandatory lens selection modal (same as eyeglass_detail)
    - Sunglasses: optional prescription power modal (same as sunglass_detail)
    """
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug,
        gender='kids',
        product_type__in=['eyeglasses', 'sunglasses'],
        is_active=True
    )

    all_images    = product.images.all().order_by('display_order')
    primary_image = all_images.filter(is_primary=True).first() or all_images.first()
    extra_images  = all_images.exclude(id=primary_image.id) if primary_image else all_images

    # Lens data for eyeglasses type
    lens_brands = LensBrand.objects.filter(is_active=True)
    lens_types  = LensType.objects.filter(is_active=True)

    # Related kids products
    related_products = Product.objects.filter(
        gender='kids',
        product_type=product.product_type,
        is_active=True
    ).exclude(id=product.id).prefetch_related('images')[:4]

    context = {
        'product':          product,
        'primary_image':    primary_image,
        'images':           extra_images,
        'variants':         product.variants.filter(is_active=True),
        'specifications':   product.specifications.all(),
        'lens_brands':      lens_brands,
        'lens_types':       lens_types,
        'related_products': related_products,
    }
    context.update(get_review_context(request, product))
    return render(request, 'kids_detail.html', context)


# ── Brand Pages ────────────────────────────────────────────────────────────────
def brand_list(request):
    """All brands listing page"""
    brands = Brand.objects.filter(is_active=True).order_by('display_order', 'name')
    return render(request, 'brand_list.html', {'brands': brands})


def brand_detail(request, slug):
    brand    = get_object_or_404(Brand, slug=slug, is_active=True)
    products = Product.objects.filter(brand=brand, is_active=True)

    product_type = request.GET.get('type')
    if product_type:
        products = products.filter(product_type=product_type)

    sort = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    products = products.order_by(sort if sort in valid_sorts else '-created_at')

    paginator = Paginator(products.select_related('brand', 'category').prefetch_related('images', 'variants'), 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'brand':        brand,
        'products':     page_obj,
        'page_obj':     page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'other_brands': Brand.objects.filter(is_active=True).exclude(id=brand.id).order_by('display_order')[:10],
        'current_sort': sort,
    }
    return render(request, 'brand_detail.html', context)


# ── Category Pages ─────────────────────────────────────────────────────────────
def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True).select_related('brand').prefetch_related('images', 'variants')

    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        products = products.filter(gender=gender)

    sort  = request.GET.get('sort', '-created_at')
    valid = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    products = products.order_by(sort if sort in valid else '-created_at')

    paginator = Paginator(products, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'category_detail.html', {
        'category':        category,
        'products':        page_obj,
        'page_obj':        page_obj,
        'is_paginated':    page_obj.has_other_pages(),
        'selected_gender': gender,
        'current_sort':    sort,
    })


# ── Search ─────────────────────────────────────────────────────────────────────
def search_view(request):
    """Search functionality"""
    query    = request.GET.get('q', '')
    products = Product.objects.none()

    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query),
            is_active=True
        ).select_related('brand', 'category').distinct()

    paginator = Paginator(products, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'query':        query,
        'products':     page_obj,
        'page_obj':     page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'count':        products.count(),
    }
    return render(request, 'search_results.html', context)


# ── Medical Lenses List ────────────────────────────────────────────────────────
def medical_lenses_list(request):
    """Medical lenses listing page."""
    queryset = LensOption.objects.filter(is_active=True).select_related(
        'lens_brand', 'lens_type'
    ).prefetch_related('coatings')

    selected_lens_brands = request.GET.getlist('lens_brand')
    if selected_lens_brands:
        queryset = queryset.filter(lens_brand__slug__in=selected_lens_brands)

    selected_lens_types = request.GET.getlist('lens_type')
    if selected_lens_types:
        queryset = queryset.filter(lens_type__slug__in=selected_lens_types)

    selected_indexes = request.GET.getlist('index')
    if selected_indexes:
        queryset = queryset.filter(index__in=selected_indexes)

    selected_coatings = request.GET.getlist('coating')
    if selected_coatings:
        queryset = queryset.filter(coatings__code__in=selected_coatings).distinct()

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator  = Paginator(queryset, 24)
    page_obj   = paginator.get_page(request.GET.get('page'))

    price_range = LensOption.objects.filter(is_active=True).aggregate(
        min_price=Min('base_price'),
        max_price=Max('base_price')
    )

    index_options = (
        LensOption.objects
        .filter(is_active=True)
        .values_list('index', flat=True)
        .distinct()
        .order_by('index')
    )

    context = {
        'lens_options':         page_obj,
        'page_obj':             page_obj,
        'is_paginated':         page_obj.has_other_pages(),
        'lens_brands':          LensBrand.objects.filter(is_active=True).order_by('name'),
        'lens_types':           LensType.objects.filter(is_active=True).order_by('name'),
        'index_options':        index_options,
        'price_range':          price_range,
        'selected_lens_brands': selected_lens_brands,
        'selected_lens_types':  selected_lens_types,
        'selected_indexes':     selected_indexes,
        'selected_coatings':    selected_coatings,
        'current_sort':         sort_option,
    }
    return render(request, 'medical_lenses_list.html', context)


# ── Medical Lens Detail ────────────────────────────────────────────────────────
def medical_lens_detail(request, pk):
    lens_option = get_object_or_404(
        LensOption.objects.select_related('lens_brand', 'lens_type')
                          .prefetch_related('coatings'),
        pk=pk, is_active=True
    )

    related_qs = LensOption.objects.filter(is_active=True).exclude(pk=pk).select_related('lens_brand', 'lens_type')
    if lens_option.lens_type:
        related_same = list(related_qs.filter(lens_type=lens_option.lens_type)[:4])
        if len(related_same) < 4:
            extra_ids = [r.id for r in related_same] + [pk]
            extra     = list(related_qs.exclude(id__in=extra_ids)[:4 - len(related_same)])
            related_lens_options = related_same + extra
        else:
            related_lens_options = related_same
    else:
        related_lens_options = list(related_qs[:4])

    context = {
        'lens_option':          lens_option,
        'related_lens_options': related_lens_options,
    }
    return render(request, 'medical_lens_detail.html', context)


# ── Accessories List ───────────────────────────────────────────────────────────
def accessories_list(request):
    """Accessories listing page with filtering"""
    queryset = Product.objects.filter(
        product_type='accessories',
        is_active=True
    ).select_related('brand', 'category').prefetch_related('images', 'variants')

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    selected_categories = request.GET.getlist('category')
    if selected_categories:
        queryset = queryset.filter(category__slug__in=selected_categories)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    price_range = Product.objects.filter(
        product_type='accessories', is_active=True
    ).aggregate(min_price=Min('base_price'), max_price=Max('base_price'))

    context = {
        'products':            page_obj,
        'page_obj':            page_obj,
        'is_paginated':        page_obj.has_other_pages(),
        'brands':              Brand.objects.filter(is_active=True).order_by('display_order', 'name'),
        'categories':          Category.objects.filter(is_active=True).order_by('name'),
        'price_range':         price_range,
        'selected_brands':     selected_brands,
        'selected_categories': selected_categories,
        'current_sort':        sort_option,
    }
    return render(request, 'accessories_list.html', context)


# ── Reading Glasses List ───────────────────────────────────────────────────────
def reading_glasses_list(request):
    """Reading glasses listing page with filtering"""
    queryset = Product.objects.filter(
        product_type='reading_glasses',
        is_active=True
    ).select_related('brand', 'category').prefetch_related('images', 'variants')

    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        queryset = queryset.filter(gender=gender)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    price_range = Product.objects.filter(
        product_type='reading_glasses', is_active=True
    ).aggregate(min_price=Min('base_price'), max_price=Max('base_price'))

    context = {
        'products':        page_obj,
        'page_obj':        page_obj,
        'is_paginated':    page_obj.has_other_pages(),
        'brands':          Brand.objects.filter(is_active=True).order_by('display_order', 'name'),
        'price_range':     price_range,
        'selected_gender': gender,
        'selected_brands': selected_brands,
        'current_sort':    sort_option,
    }
    return render(request, 'reading_glasses_list.html', context)


# ── Kids List ──────────────────────────────────────────────────────────────────
def kids_list(request):
    """
    Kids eyeglasses/sunglasses listing page.
    Filters products where gender='kids' across eyeglasses and sunglasses.
    """
    queryset = Product.objects.filter(
        gender='kids',
        is_active=True
    ).select_related('brand', 'category').prefetch_related('images', 'variants')

    product_type = request.GET.get('type', 'all')
    if product_type != 'all':
        queryset = queryset.filter(product_type=product_type)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(base_price__lte=max_price)

    sort_option = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'base_price', '-base_price', 'name', '-name']
    queryset = queryset.order_by(sort_option if sort_option in valid_sorts else '-created_at')

    paginator = Paginator(queryset, 24)
    page_obj  = paginator.get_page(request.GET.get('page'))

    price_range = Product.objects.filter(
        gender='kids', is_active=True
    ).aggregate(min_price=Min('base_price'), max_price=Max('base_price'))

    context = {
        'products':        page_obj,
        'page_obj':        page_obj,
        'is_paginated':    page_obj.has_other_pages(),
        'brands':          Brand.objects.filter(is_active=True).order_by('display_order', 'name'),
        'price_range':     price_range,
        'selected_type':   product_type,
        'selected_brands': selected_brands,
        'current_sort':    sort_option,
    }
    return render(request, 'kids_list.html', context)


# ── AJAX Endpoints ─────────────────────────────────────────────────────────────
def get_lens_options(request):
    """Get lens options based on lens type and brand"""
    from django.http import JsonResponse

    lens_type_id  = request.GET.get('lens_type_id')
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
                'powers':        list(powers)
            })
        else:
            return JsonResponse({
                'power_enabled': False,
                'message':       'Power not available for this color'
            })
    except ContactLensColor.DoesNotExist:
        return JsonResponse({'error': 'Color not found'}, status=404)