from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from catalog.models import Product, Brand, Category

@login_required
def dashboard(request):
    context = {
        "products": Product.objects.count(),
        "brands": Brand.objects.count(),
        "categories": Category.objects.count(),
    }
    return render(request, "admin-dashboard.html", context)

@login_required
def add_category_page(request):
   
    return render(request, "category_add.html")