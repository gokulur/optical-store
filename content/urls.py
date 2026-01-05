from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
 
    
    # Store Locations
    path('locations/', views.StoreLocationListView.as_view(), name='store_locations'),
    path('location/<int:pk>/', views.store_location_detail, name='store_location_detail'),
    
    # Eye Test Booking
    path('book-eye-test/', views.eye_test_booking, name='eye_test_booking'),
    path('booking-confirmation/<int:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    
    # AJAX Endpoints
    path('api/available-times/', views.get_available_times, name='get_available_times'),
    path('api/location-details/', views.get_location_details, name='get_location_details'),
    path('api/newsletter-subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
]