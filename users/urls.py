from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication
    path('register/', views.user_register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    
    # Dashboard & Profile
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.account_settings, name='settings'),
    path('change-password/', views.change_password, name='change_password'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # Addresses
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.address_create, name='address_create'),
    path('addresses/<int:address_id>/edit/', views.address_edit, name='address_edit'),
    path('addresses/<int:address_id>/delete/', views.address_delete, name='address_delete'),
    path('addresses/<int:address_id>/set-default/', views.set_default_address, name='set_default_address'),
]