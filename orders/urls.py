# orders/urls.py - WITH PAYMENT ROUTES
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('place-order/', views.place_order, name='place_order'),
    path('confirmation/<str:order_number>/', views.order_confirmation, name='order_confirmation'),
    
    # Stripe Payment
    path('payment/stripe/<str:order_number>/', views.stripe_payment, name='stripe_payment'),
    path('payment/stripe/<str:order_number>/confirm/', views.stripe_payment_confirm, name='stripe_payment_confirm'),
    
    # Razorpay Payment
    path('payment/razorpay/<str:order_number>/', views.razorpay_payment, name='razorpay_payment'),
    path('payment/razorpay/verify/', views.razorpay_payment_verify, name='razorpay_payment_verify'),
    
    # PayPal Payment
    path('payment/paypal/<str:order_number>/', views.paypal_payment, name='paypal_payment'),
    path('payment/paypal/<str:order_number>/execute/', views.paypal_execute, name='paypal_execute'),
    
    # Order Management
    path('', views.order_list, name='order_list'),
    path('<str:order_number>/', views.order_detail, name='order_detail'),
    path('<str:order_number>/track/', views.track_order, name='track_order'),
    path('<str:order_number>/cancel/', views.cancel_order, name='cancel_order'),
    
    # AJAX
    path('api/<str:order_number>/status/', views.get_order_status, name='get_order_status'),
]