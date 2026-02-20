from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    # Full wishlist page (GET, login required)
    path('', views.wishlist_view, name='wishlist'),

    # Toggle add/remove — heart button uses this (POST only)
    path('toggle/<int:product_id>/', views.toggle_wishlist, name='toggle'),

    # Legacy toggle via POST body (no product_id in URL)
    path('toggle/', views.toggle_wishlist_post, name='toggle_post'),

    # Hard remove (GET or POST)
    path('remove/<int:product_id>/', views.remove_from_wishlist, name='remove'),

    # Clear entire wishlist (POST only)
    path('clear/', views.clear_wishlist, name='clear'),

    # Move single item to cart (POST only)
    path('move-to-cart/<int:product_id>/', views.move_to_cart, name='move_to_cart'),

    # Move all items to cart (POST only)
    path('move-all-to-cart/', views.move_all_to_cart, name='move_all_to_cart'),

    # Badge count helper (GET)
    path('count/', views.wishlist_count, name='count'),
]