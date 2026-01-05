from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # Cart View
    path('', views.cart_view, name='cart_view'),
    
    # Add to Cart
    path('add/', views.add_to_cart, name='add_to_cart'),
    path('add-eyeglass/', views.add_eyeglass_to_cart, name='add_eyeglass_to_cart'),
    path('add-sunglass/', views.add_sunglass_to_cart, name='add_sunglass_to_cart'),
    path('add-contact-lens/', views.add_contact_lens_to_cart, name='add_contact_lens_to_cart'),
    
    # Update/Remove
    path('update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear/', views.clear_cart, name='clear_cart'),
    
    # AJAX Endpoints
    path('api/count/', views.get_cart_count, name='get_cart_count'),
    path('api/summary/', views.get_cart_summary, name='get_cart_summary'),
    
   
]