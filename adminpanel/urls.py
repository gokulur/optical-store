from django.urls import path
from .import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("add-category/", views.add_category_page, name="add_category_page"),
    path("categories/", views.category_list, name="category_list"),
]

