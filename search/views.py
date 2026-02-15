# search/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator

from .models import SearchQuery, PopularSearch
from catalog.models import Product, Brand, Category


def search_view(request):
    """Main search page"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        context = {
            'query': '',
            'products': [],
            'total_results': 0,
            'popular_searches': PopularSearch.objects.filter(is_active=True)[:10],
        }
        return render(request, 'search.html', context)
    
    # Get filters
    brand_filter = request.GET.get('brand')
    category_filter = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort', 'relevance')
    
    # Search products
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(category__name__icontains=query),
        is_active=True
    ).select_related('brand', 'category').distinct()
    
    # Apply filters
    filters_applied = {}
    
    if brand_filter:
        products = products.filter(brand__slug=brand_filter)
        filters_applied['brand'] = brand_filter
    
    if category_filter:
        products = products.filter(category__slug=category_filter)
        filters_applied['category'] = category_filter
    
    if min_price:
        products = products.filter(base_price__gte=min_price)
        filters_applied['min_price'] = min_price
    
    if max_price:
        products = products.filter(base_price__lte=max_price)
        filters_applied['max_price'] = max_price
    
    # Sorting
    if sort_by == 'price_low':
        products = products.order_by('base_price')
    elif sort_by == 'price_high':
        products = products.order_by('-base_price')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:  # relevance
        # TODO: Implement relevance scoring
        products = products.order_by('-created_at')
    
    total_results = products.count()
    
    # Log search query
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    
    SearchQuery.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=session_key,
        query=query,
        results_count=total_results,
        filters_applied=filters_applied
    )
    
    # Pagination
    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get brands and categories for filters
    available_brands = Brand.objects.filter(
        id__in=Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True
        ).values_list('brand_id', flat=True)
    )
    
    available_categories = Category.objects.filter(
        id__in=Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True
        ).values_list('category_id', flat=True)
    )
    
    context = {
        'query': query,
        'products': page_obj,
        'total_results': total_results,
        'available_brands': available_brands,
        'available_categories': available_categories,
        'filters_applied': filters_applied,
        'sort_by': sort_by,
    }
    
    return render(request, 'search.html', context)


@require_GET
def autocomplete(request):
    """Autocomplete suggestions (AJAX)"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    # Get product suggestions
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(brand__name__icontains=query),
        is_active=True
    ).select_related('brand')[:5]
    
    product_suggestions = [
        {
            'type': 'product',
            'name': product.name,
            'brand': product.brand.name if product.brand else '',
            'url': f'/product/{product.slug}/',
            'image': product.images.first().image.url if product.images.first() else None,
            'price': str(product.base_price)
        }
        for product in products
    ]
    
    # Get brand suggestions
    brands = Brand.objects.filter(
        name__icontains=query,
        is_active=True
    )[:3]
    
    brand_suggestions = [
        {
            'type': 'brand',
            'name': brand.name,
            'url': f'/brand/{brand.slug}/'
        }
        for brand in brands
    ]
    
    # Get category suggestions
    categories = Category.objects.filter(
        name__icontains=query,
        is_active=True
    )[:3]
    
    category_suggestions = [
        {
            'type': 'category',
            'name': category.name,
            'url': f'/category/{category.slug}/'
        }
        for category in categories
    ]
    
    # Get popular searches
    popular = PopularSearch.objects.filter(
        keyword__icontains=query,
        is_active=True
    )[:3]
    
    popular_suggestions = [
        {
            'type': 'popular',
            'name': search.keyword,
            'url': f'/search/?q={search.keyword}'
        }
        for search in popular
    ]
    
    all_suggestions = (
        product_suggestions + 
        brand_suggestions + 
        category_suggestions + 
        popular_suggestions
    )
    
    return JsonResponse({'suggestions': all_suggestions[:10]})


@require_GET
def search_suggestions(request):
    """Get search suggestions for search bar"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        # Return popular searches
        popular = PopularSearch.objects.filter(is_active=True)[:5]
        suggestions = [{'keyword': p.keyword} for p in popular]
        return JsonResponse({'suggestions': suggestions})
    
    # Get recent searches by user
    recent_searches = []
    if request.user.is_authenticated:
        recent = SearchQuery.objects.filter(
            user=request.user,
            query__icontains=query
        ).values('query').distinct()[:3]
        recent_searches = [{'keyword': s['query'], 'type': 'recent'} for s in recent]
    
    # Get popular matching searches
    popular = PopularSearch.objects.filter(
        keyword__icontains=query,
        is_active=True
    )[:5]
    popular_searches = [{'keyword': p.keyword, 'type': 'popular'} for p in popular]
    
    # Get product name matches
    products = Product.objects.filter(
        name__icontains=query,
        is_active=True
    ).values('name')[:3]
    product_searches = [{'keyword': p['name'], 'type': 'product'} for p in products]
    
    all_suggestions = recent_searches + popular_searches + product_searches
    
    return JsonResponse({'suggestions': all_suggestions[:8]})


def search_history(request):
    """View user's search history"""
    if not request.user.is_authenticated:
        return render(request, 'search_history.html', {'searches': []})
    
    searches = SearchQuery.objects.filter(
        user=request.user
    ).order_by('-created_at')[:50]
    
    context = {
        'searches': searches,
    }
    
    return render(request, 'search_history.html', context)


def clear_search_history(request):
    """Clear user's search history"""
    if request.user.is_authenticated:
        SearchQuery.objects.filter(user=request.user).delete()
    
    return JsonResponse({'success': True})


def trending_searches(request):
    """Get trending/popular searches"""
    # Get most searched queries in last 30 days
    from django.utils import timezone
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    trending = SearchQuery.objects.filter(
        created_at__gte=thirty_days_ago
    ).values('query').annotate(
        search_count=Count('id')
    ).order_by('-search_count')[:20]
    
    context = {
        'trending': trending,
    }
    
    return render(request, 'trending.html', context)


# Analytics (for admin)
def search_analytics(request):
    """Search analytics dashboard (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from django.utils import timezone
    from datetime import timedelta
    
    # Last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Top searches
    top_searches = SearchQuery.objects.filter(
        created_at__gte=thirty_days_ago
    ).values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Searches with no results
    no_results = SearchQuery.objects.filter(
        created_at__gte=thirty_days_ago,
        results_count=0
    ).values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Total searches
    total_searches = SearchQuery.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()
    
    context = {
        'top_searches': top_searches,
        'no_results': no_results,
        'total_searches': total_searches,
    }
    
    return render(request, 'analytics.html', context)


 
