from django.contrib.auth.decorators import login_required
from django.shortcuts import render
 

@login_required
def dashboard(request):
 
    return render(request, "admin-dashboard.html")

@login_required
def add_category_page(request):
   
    return render(request, "category_add.html")

@login_required
def category_list(request):
   
    return render(request, "category_list.html")