from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Product Reviews
    path('product/<slug:product_slug>/', views.product_reviews, name='product_reviews'),
    
    # Write/Edit Reviews
    path('write/<slug:product_slug>/', views.write_review, name='write_review'),
    path('edit/<int:review_id>/', views.edit_review, name='edit_review'),
    path('delete/<int:review_id>/', views.delete_review, name='delete_review'),
    
    # My Reviews
    path('my-reviews/', views.my_reviews, name='my_reviews'),
    
    # Helpfulness
    path('<int:review_id>/helpful/', views.mark_helpful, name='mark_helpful'),
    
    # AJAX Endpoints
    path('api/rating/<slug:product_slug>/', views.get_product_rating, name='get_product_rating'),
    path('api/summary/<slug:product_slug>/', views.get_reviews_summary, name='get_reviews_summary'),
    
    # Admin/Moderation (would typically be in admin interface)
    path('admin/pending/', views.reviews_pending_moderation, name='pending_moderation'),
    path('admin/approve/<int:review_id>/', views.approve_review, name='approve_review'),
    path('admin/reject/<int:review_id>/', views.reject_review, name='reject_review'),
    path('admin/feature/<int:review_id>/', views.feature_review, name='feature_review'),
]