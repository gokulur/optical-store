from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.db.models import Q, Min, Max
from django.contrib.auth.decorators import login_required
from .models import (
    Product, Category, Brand, ProductVariant, 
    ContactLensProduct, ContactLensColor, LensBrand, 
    LensType, LensOption
)


# Home Page
def home_view(request):
    """Homepage with banners and featured products"""
    featured_products = Product.objects.filter(is_featured=True, is_active=True)[:8]
    categories = Category.objects.filter(is_active=True, parent=None)
    brands = Brand.objects.filter(is_active=True)[:12]
    
    context = {
        'featured_products': featured_products,
        'categories': categories,
        'brands': brands,
    }
    return render(request, 'home.html', context)


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
class ProductDetailView(DetailView):
    """Product detail page"""
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'
    slug_field = 'slug'

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related(
            'brand', 'category'
        ).prefetch_related(
            'variants', 'images', 'specifications'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        
        # Get variants
        context['variants'] = product.variants.filter(is_active=True)
        
        # Get default variant
        context['default_variant'] = product.variants.filter(
            is_default=True, is_active=True
        ).first()
        
        # Get images
        context['images'] = product.images.all()
        
        # Get specifications
        context['specifications'] = product.specifications.all()
        
        # Related products
        context['related_products'] = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(id=product.id)[:4]
        
        # For contact lenses, get color options
        if product.product_type == 'contact_lenses':
            try:
                contact_lens = product.contact_lens
                context['contact_lens'] = contact_lens
                context['colors'] = contact_lens.colors.filter(is_active=True)
            except ContactLensProduct.DoesNotExist:
                pass
        
        return context


# Sunglass Detail
def sunglass_detail(request, slug):
    """Sunglass product detail page"""
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug,
        product_type='sunglasses',
        is_active=True
    )
    
    context = {
        'product': product,
        'variants': product.variants.filter(is_active=True),
        'images': product.images.all(),
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
    """Eyeglass product detail page"""
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category'),
        slug=slug,
        product_type='eyeglasses',
        is_active=True
    )
    
    # Get lens options for selection
    lens_brands = LensBrand.objects.filter(is_active=True)
    lens_types = LensType.objects.filter(is_active=True)
    
    context = {
        'product': product,
        'variants': product.variants.filter(is_active=True),
        'images': product.images.all(),
        'specifications': product.specifications.all(),
        'lens_brands': lens_brands,
        'lens_types': lens_types,
        'related_products': Product.objects.filter(
            category=product.category,
            product_type='eyeglasses',
            is_active=True
        ).exclude(id=product.id)[:4]
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
    """Brand detail page with products"""
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    products = Product.objects.filter(brand=brand, is_active=True)
    
    # Filter by product type
    product_type = request.GET.get('type')
    if product_type:
        products = products.filter(product_type=product_type)
    
    context = {
        'brand': brand,
        'products': products,
    }
    return render(request, 'brand_detail.html', context)


# Category Pages
def category_detail(request, slug):
    """Category page with products"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True)
    
    # Filter by gender
    gender = request.GET.get('gender', 'all')
    if gender != 'all':
        products = products.filter(gender=gender)
    
    context = {
        'category': category,
        'products': products,
        'selected_gender': gender,
    }
    return render(request, 'category_detail.html', context)


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