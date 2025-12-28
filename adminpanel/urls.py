from django.urls import path
from .import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_add, name="add_category_page"),
    path("categories/edit/<int:category_id>/", views.category_edit, name="category_edit"),
    path("categories/delete/<int:category_id>/", views.category_delete, name="delete_category"),

    # Brands
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/add/", views.brand_add, name="add_brand_page"),
    path("brands/edit/<int:brand_id>/", views.brand_edit, name="brand_edit"),
    path("brands/delete/<int:brand_id>/", views.brand_delete, name="delete_brand"),

    # Products
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/edit/<int:product_id>/", views.product_edit, name="product_edit"),
    path("products/delete/<int:product_id>/", views.product_delete, name="product_delete"),

    # lens management
    path("lenses/", views.lens_list, name="lens_list"),
    path("lenses/add/", views.lens_add, name="lens_add"),
    path("lenses/edit/<int:lens_id>/", views.lens_edit, name="lens_edit"),
    path("lenses/delete/<int:lens_id>/", views.lens_delete, name="lens_delete"),

    # lens category
    path("lens-categories/", views.lens_category_list, name="lens_category_list"),
    path("lens-categories/add/", views.lens_category_add, name="lens_category_add"),
    # path("lens-categories/edit/<int:category_id>/", views.lens_category_edit, name="lens_category_edit"),
    path("lens-categories/delete/<int:category_id>/", views.lens_category_delete, name="lens_category_delete"),
    
]

