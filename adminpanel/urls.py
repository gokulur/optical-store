from django.urls import path
from .import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.add_category_page, name="add_category_page"),
    path("categories/edit/<int:category_id>/", views.category_edit, name="category_edit"),
]

