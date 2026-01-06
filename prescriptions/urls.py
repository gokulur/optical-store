from django.urls import path
from . import views

app_name = 'prescriptions'

urlpatterns = [
    # Main Views
    path('', views.prescription_list, name='prescription_list'),
    path('<int:prescription_id>/', views.prescription_detail, name='prescription_detail'),
    path('create/', views.prescription_create, name='prescription_create'),
    path('<int:prescription_id>/edit/', views.prescription_edit, name='prescription_edit'),
    path('<int:prescription_id>/delete/', views.prescription_delete, name='prescription_delete'),
    
    # Upload
    path('upload/', views.prescription_upload, name='prescription_upload'),
    
    # History
    path('history/', views.prescription_history, name='prescription_history'),
    
    # Actions
    path('<int:prescription_id>/set-default/', views.set_default_prescription, name='set_default'),
    
    # AJAX Endpoints
    path('api/<int:prescription_id>/data/', views.get_prescription_data, name='get_prescription_data'),
    path('api/default/', views.get_default_prescription, name='get_default_prescription'),
]