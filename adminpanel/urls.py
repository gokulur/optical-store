from django.urls import path
from .import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.add_category_page, name="add_category_page"),
    path("categories/edit/<int:category_id>/", views.category_edit, name="category_edit"),
    path("categories/delete/<int:category_id>/", views.category_delete, name="delete_category"),

    # Brands
    path("brands/", views.brand_list, name="brand_list"),

]

