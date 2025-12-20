from django.contrib.auth.decorators import login_required
from django.shortcuts import render
 

 
def dashboard(request):
 
    return render(request, "admin-dashboard.html")

 
def add_category_page(request):
   
    return render(request, "category_add.html")

 
def category_list(request):
   
    return render(request, "category_list.html")