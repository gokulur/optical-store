 
from django.db.models import Avg, Count, Q
from .models import Review


def get_review_context(request, product):
    """
    Returns a dict of review context variables for any product detail view.
    
    Usage in views.py:
        from reviews.reviews_context import get_review_context
        
        def sunglass_detail(request, slug):
            product = get_object_or_404(...)
            context = {
                'product': product,
                ...your existing context...
            }
            context.update(get_review_context(request, product))
            return render(request, 'sunglass_detail.html', context)
    """

    # Rating statistics
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

    # Percentage breakdown for the bar chart
    total = rating_stats['total_reviews'] or 1
    rating_percentages = {
        5: round((rating_stats['five_star'] / total) * 100),
        4: round((rating_stats['four_star'] / total) * 100),
        3: round((rating_stats['three_star'] / total) * 100),
        2: round((rating_stats['two_star'] / total) * 100),
        1: round((rating_stats['one_star'] / total) * 100),
    }

    # Can this user write a review?
    can_review = False
    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            product=product,
            customer=request.user
        ).first()
        can_review = not user_review

    return {
        'rating_stats': rating_stats,
        'rating_percentages': rating_percentages,
        'can_review': can_review,
        'user_review': user_review,
    }