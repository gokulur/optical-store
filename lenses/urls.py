from django.urls import path
from . import views

app_name = 'lenses'

urlpatterns = [
    # Lens Categories & Options
    path('categories/', views.lens_categories_view, name='categories'),
    path('guide/', views.lens_guide_view, name='guide'),
    path('comparison/', views.lens_comparison_view, name='comparison'),
    
    # AJAX Endpoints - Get Options
    path('api/options-by-category/', views.get_lens_options_by_category, name='get_options_by_category'),
    path('api/option-details/', views.get_lens_option_details, name='get_option_details'),
    path('api/addon-details/', views.get_addon_details, name='get_addon_details'),
    path('api/reading-powers/', views.get_reading_powers, name='get_reading_powers'),
    
    # AJAX Endpoints - Sunglass Lenses
    path('api/sunglass-options/', views.get_sunglass_lens_options, name='get_sunglass_options'),
    
    # AJAX Endpoints - Calculations & Validation
    path('api/calculate-price/', views.calculate_lens_price, name='calculate_price'),
    path('api/validate-prescription/', views.validate_prescription, name='validate_prescription'),
    
    # AJAX Endpoints - Recommendations
    path('api/recommendations/', views.get_lens_recommendation, name='get_recommendation'),
]