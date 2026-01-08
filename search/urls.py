from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    # Main Search
    path('', views.search_view, name='search'),
    
    # AJAX Endpoints
    path('autocomplete/', views.autocomplete, name='autocomplete'),
    path('suggestions/', views.search_suggestions, name='suggestions'),
    
    # Search History
    path('history/', views.search_history, name='history'),
    path('history/clear/', views.clear_search_history, name='clear_history'),
    
    # Trending
    path('trending/', views.trending_searches, name='trending'),
    
    # Analytics (Admin)
    path('analytics/', views.search_analytics, name='analytics'),
]