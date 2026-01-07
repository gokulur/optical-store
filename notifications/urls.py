# ==================== URLS ====================
# notifications/urls.py
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # User Notifications
    path('', views.notification_list, name='notification_list'),
    path('<int:notification_id>/', views.notification_detail, name='notification_detail'),
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # Stock Alerts
    path('stock-alert/create/', views.create_stock_alert, name='create_stock_alert'),
    path('stock-alerts/', views.my_stock_alerts, name='my_stock_alerts'),
    path('stock-alert/<int:alert_id>/cancel/', views.cancel_stock_alert, name='cancel_stock_alert'),
]