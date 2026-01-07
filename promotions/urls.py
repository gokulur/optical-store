# promotions/urls.py
from django.urls import path
from . import views

app_name = 'promotions'

urlpatterns = [
    path('apply/', views.apply_coupon, name='apply_coupon'),
    path('remove/', views.remove_coupon, name='remove_coupon'),
    path('my-coupons/', views.my_coupons, name='my_coupons'),
    path('', views.active_promotions, name='promotions'),
]