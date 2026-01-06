from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('place-order/', views.place_order, name='place_order'),
    path('confirmation/<str:order_number>/', views.order_confirmation, name='order_confirmation'),
    
    # Order Management
    path('', views.order_list, name='order_list'),
    path('<str:order_number>/', views.order_detail, name='order_detail'),
    path('<str:order_number>/track/', views.track_order, name='track_order'),
    path('<str:order_number>/cancel/', views.cancel_order, name='cancel_order'),
    path('<str:order_number>/reorder/', views.reorder, name='reorder'),
    
    # AJAX
    path('api/<str:order_number>/status/', views.get_order_status, name='get_order_status'),
]