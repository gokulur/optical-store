# wishlist/urls.py

from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    # ── Full wishlist page ────────────────────────────────────────
    path('', views.wishlist_view, name='wishlist'),

    # ── Toggle (add/remove) — two URL patterns ────────────────────
    # 1. With product_id in URL  →  /wishlist/toggle/42/
    path('toggle/<int:product_id>/', views.toggle_wishlist, name='toggle'),

    # 2. POST-body only  →  /wishlist/toggle/   (legacy / base.html AJAX)
    path('toggle/', views.toggle_wishlist_post, name='toggle_post'),

    # ── Hard remove ───────────────────────────────────────────────
    path('remove/<int:product_id>/', views.remove_from_wishlist, name='remove'),

    # ── Clear all ─────────────────────────────────────────────────
    path('clear/', views.clear_wishlist, name='clear'),

    # ── Move to cart ──────────────────────────────────────────────
    path('move-to-cart/<int:product_id>/', views.move_to_cart, name='move_to_cart'),
    path('move-all-to-cart/', views.move_all_to_cart, name='move_all_to_cart'),

    # ── Count badge (AJAX) ────────────────────────────────────────
    path('count/', views.wishlist_count, name='count'),
]

 