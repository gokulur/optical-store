from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Home
    path('', views.home_view, name='home'),

    # Product Lists
    path('sunglasses/',      views.sunglasses_list,       name='sunglasses_list'),
    path('eyeglasses/',      views.eyeglasses_list,       name='eyeglasses_list'),
    path('contact-lenses/',  views.contact_lenses_list,   name='contact_lenses_list'),
    path('medical-lenses/',  views.medical_lenses_list,   name='medical_lenses_list'),
    path('accessories/',     views.accessories_list,      name='accessories_list'),
    path('reading-glasses/', views.reading_glasses_list,  name='reading_glasses_list'),
    path('kids/',            views.kids_list,             name='kids_list'),

    # Generic product list (by type slug)
    path('products/<str:product_type>/', views.ProductListView.as_view(), name='product_list'),

    # Product Details
    path('sunglass/<slug:slug>/',     views.sunglass_detail,     name='sunglass_detail'),
    path('eyeglass/<slug:slug>/',     views.eyeglass_detail,     name='eyeglass_detail'),
    path('contact-lens/<slug:slug>/', views.contact_lens_detail, name='contact_lens_detail'),
    path('medical-lens/<int:pk>/',    views.medical_lens_detail, name='medical_lens_detail'),
    path('accessory/<slug:slug>/',    views.accessory_detail,    name='accessory_detail'),
    path('kids/<slug:slug>/',         views.kids_detail,         name='kids_detail'),

    # Brands
    path('brands/',              views.brand_list,    name='brand_list'),
    path('brand/<slug:slug>/',   views.brand_detail,  name='brand_detail'),

    # Categories
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # Search
    path('search-result', views.search_view, name='search'),

    # AJAX endpoints
    path('api/lens-options/',         views.get_lens_options,       name='get_lens_options'),
    path('api/contact-lens-powers/',  views.get_contact_lens_powers, name='get_contact_lens_powers'),
]