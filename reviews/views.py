from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator

from .models import Review, ReviewImage, ReviewHelpfulness
from catalog.models import Product


def product_reviews(request, product_slug):
    """Display all reviews for a product"""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    
    # Get approved reviews
    reviews = Review.objects.filter(
        product=product,
        is_approved=True
    ).select_related('customer').prefetch_related('images')
    
    # Filter by rating
    rating_filter = request.GET.get('rating')
    if rating_filter and rating_filter != 'all':
        reviews = reviews.filter(rating=int(rating_filter))
    
    # Filter by verified purchase
    verified_only = request.GET.get('verified') == 'true'
    if verified_only:
        reviews = reviews.filter(is_verified_purchase=True)
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by == 'helpful':
        reviews = reviews.order_by('-helpful_count', '-created_at')
    elif sort_by == 'rating_high':
        reviews = reviews.order_by('-rating', '-created_at')
    elif sort_by == 'rating_low':
        reviews = reviews.order_by('rating', '-created_at')
    else:
        reviews = reviews.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate rating statistics
    rating_stats = Review.objects.filter(
        product=product,
        is_approved=True
    ).aggregate(
        average_rating=Avg('rating'),
        total_reviews=Count('id'),
        five_star=Count('id', filter=Q(rating=5)),
        four_star=Count('id', filter=Q(rating=4)),
        three_star=Count('id', filter=Q(rating=3)),
        two_star=Count('id', filter=Q(rating=2)),
        one_star=Count('id', filter=Q(rating=1)),
    )
    
    # Calculate percentages
    total = rating_stats['total_reviews'] or 1
    rating_percentages = {
        5: (rating_stats['five_star'] / total) * 100,
        4: (rating_stats['four_star'] / total) * 100,
        3: (rating_stats['three_star'] / total) * 100,
        2: (rating_stats['two_star'] / total) * 100,
        1: (rating_stats['one_star'] / total) * 100,
    }
    
    # Check if user can review
    can_review = False
    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            product=product,
            customer=request.user
        ).first()
        
        # Check if user has purchased this product
        # Simplified check - you can make this more sophisticated
        can_review = not user_review
    
    context = {
        'product': product,
        'reviews': page_obj,
        'rating_stats': rating_stats,
        'rating_percentages': rating_percentages,
        'can_review': can_review,
        'user_review': user_review,
        'current_rating_filter': rating_filter,
        'verified_only': verified_only,
        'sort_by': sort_by,
    }
    
    return render(request, 'reviews/product_reviews.html', context)


@login_required
def write_review(request, product_slug):
    """Write a review for a product"""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    
    # Check if user already reviewed this product
    existing_review = Review.objects.filter(
        product=product,
        customer=request.user
    ).first()
    
    if existing_review:
        messages.warning(request, 'You have already reviewed this product.')
        return redirect('reviews:edit_review', review_id=existing_review.id)
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            title = request.POST.get('title', '')
            comment = request.POST.get('comment')
            
            # Validate
            if not (1 <= rating <= 5):
                raise ValueError('Invalid rating')
            
            if not comment or len(comment.strip()) < 10:
                messages.error(request, 'Please write a review of at least 10 characters.')
                return redirect('reviews:write_review', product_slug=product_slug)
            
            # Create review
            review = Review.objects.create(
                product=product,
                customer=request.user,
                rating=rating,
                title=title,
                comment=comment,
                is_verified_purchase=False,  # Check against orders
                is_approved=False  # Requires moderation
            )
            
            # Handle image uploads
            images = request.FILES.getlist('images')
            for image in images[:5]:  # Limit to 5 images
                ReviewImage.objects.create(
                    review=review,
                    image=image
                )
            
            messages.success(request, 'Thank you for your review! It will be published after moderation.')
            return redirect('catalog:product_detail', slug=product_slug)
            
        except Exception as e:
            messages.error(request, f'Error submitting review: {str(e)}')
    
    context = {
        'product': product,
    }
    
    return render(request, 'reviews/write_review.html', context)


@login_required
def edit_review(request, review_id):
    """Edit existing review"""
    review = get_object_or_404(Review, id=review_id, customer=request.user)
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            title = request.POST.get('title', '')
            comment = request.POST.get('comment')
            
            # Validate
            if not (1 <= rating <= 5):
                raise ValueError('Invalid rating')
            
            if not comment or len(comment.strip()) < 10:
                messages.error(request, 'Please write a review of at least 10 characters.')
                return redirect('reviews:edit_review', review_id=review_id)
            
            # Update review
            review.rating = rating
            review.title = title
            review.comment = comment
            review.is_approved = False  # Requires re-moderation
            review.save()
            
            # Handle new image uploads
            new_images = request.FILES.getlist('images')
            for image in new_images[:5]:
                ReviewImage.objects.create(
                    review=review,
                    image=image
                )
            
            # Handle image deletions
            delete_image_ids = request.POST.getlist('delete_images')
            if delete_image_ids:
                ReviewImage.objects.filter(
                    id__in=delete_image_ids,
                    review=review
                ).delete()
            
            messages.success(request, 'Your review has been updated!')
            return redirect('catalog:product_detail', slug=review.product.slug)
            
        except Exception as e:
            messages.error(request, f'Error updating review: {str(e)}')
    
    context = {
        'review': review,
        'product': review.product,
        'is_edit': True,
    }
    
    return render(request, 'reviews/write_review.html', context)


@login_required
@require_POST
def delete_review(request, review_id):
    """Delete a review"""
    review = get_object_or_404(Review, id=review_id, customer=request.user)
    product_slug = review.product.slug
    
    review.delete()
    messages.success(request, 'Your review has been deleted.')
    
    return redirect('catalog:product_detail', slug=product_slug)


@login_required
def my_reviews(request):
    """List all reviews by the current user"""
    reviews = Review.objects.filter(
        customer=request.user
    ).select_related('product').prefetch_related('images').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reviews': page_obj,
    }
    
    return render(request, 'reviews/my_reviews.html', context)


@login_required
@require_POST
def mark_helpful(request, review_id):
    """Mark a review as helpful or not helpful"""
    review = get_object_or_404(Review, id=review_id, is_approved=True)
    is_helpful = request.POST.get('is_helpful') == 'true'
    
    # Check if user already voted
    vote, created = ReviewHelpfulness.objects.get_or_create(
        review=review,
        user=request.user,
        defaults={'is_helpful': is_helpful}
    )
    
    if not created:
        # Update existing vote
        if vote.is_helpful != is_helpful:
            # Remove old vote count
            if vote.is_helpful:
                review.helpful_count = max(0, review.helpful_count - 1)
            else:
                review.not_helpful_count = max(0, review.not_helpful_count - 1)
            
            # Update vote
            vote.is_helpful = is_helpful
            vote.save()
    
    # Update review counts
    if is_helpful:
        review.helpful_count += 1
    else:
        review.not_helpful_count += 1
    
    review.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'helpful_count': review.helpful_count,
            'not_helpful_count': review.not_helpful_count
        })
    
    messages.success(request, 'Thank you for your feedback!')
    return redirect('reviews:product_reviews', product_slug=review.product.slug)


@require_GET
def get_product_rating(request, product_slug):
    """Get product rating summary (AJAX)"""
    product = get_object_or_404(Product, slug=product_slug)
    
    stats = Review.objects.filter(
        product=product,
        is_approved=True
    ).aggregate(
        average_rating=Avg('rating'),
        total_reviews=Count('id')
    )
    
    return JsonResponse({
        'average_rating': round(stats['average_rating'] or 0, 1),
        'total_reviews': stats['total_reviews'],
    })


@require_GET
def get_reviews_summary(request, product_slug):
    """Get detailed reviews summary (AJAX)"""
    product = get_object_or_404(Product, slug=product_slug)
    
    stats = Review.objects.filter(
        product=product,
        is_approved=True
    ).aggregate(
        average_rating=Avg('rating'),
        total_reviews=Count('id'),
        five_star=Count('id', filter=Q(rating=5)),
        four_star=Count('id', filter=Q(rating=4)),
        three_star=Count('id', filter=Q(rating=3)),
        two_star=Count('id', filter=Q(rating=2)),
        one_star=Count('id', filter=Q(rating=1)),
        verified_count=Count('id', filter=Q(is_verified_purchase=True)),
    )
    
    # Get featured reviews
    featured_reviews = Review.objects.filter(
        product=product,
        is_approved=True,
        is_featured=True
    ).select_related('customer').values(
        'id', 'rating', 'title', 'comment', 
        'customer__first_name', 'is_verified_purchase',
        'created_at', 'helpful_count'
    )[:3]
    
    return JsonResponse({
        'stats': {
            'average_rating': round(stats['average_rating'] or 0, 1),
            'total_reviews': stats['total_reviews'],
            'five_star': stats['five_star'],
            'four_star': stats['four_star'],
            'three_star': stats['three_star'],
            'two_star': stats['two_star'],
            'one_star': stats['one_star'],
            'verified_count': stats['verified_count'],
        },
        'featured_reviews': list(featured_reviews)
    })


def reviews_pending_moderation(request):
    """Admin view for reviews pending moderation"""
    # This would typically be in an admin interface
    if not request.user.is_staff:
        messages.error(request, 'Access denied')
        return redirect('catalog:home')
    
    pending_reviews = Review.objects.filter(
        is_approved=False
    ).select_related('product', 'customer').order_by('-created_at')
    
    paginator = Paginator(pending_reviews, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reviews': page_obj,
    }
    
    return render(request, 'reviews/pending_moderation.html', context)


@require_POST
def approve_review(request, review_id):
    """Approve a review (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = True
    review.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Review approved successfully!')
    return redirect('reviews:pending_moderation')


@require_POST
def reject_review(request, review_id):
    """Reject/delete a review (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Review rejected and deleted.')
    return redirect('reviews:pending_moderation')


@require_POST
def feature_review(request, review_id):
    """Feature/unfeature a review (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    review = get_object_or_404(Review, id=review_id)
    review.is_featured = not review.is_featured
    review.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_featured': review.is_featured
        })
    
    status = 'featured' if review.is_featured else 'unfeatured'
    messages.success(request, f'Review {status} successfully!')
    return redirect('reviews:pending_moderation')