from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import Banner, Page, StoreLocation, EyeTestBooking
from django.db import models


# Store Locations
class StoreLocationListView(ListView):
    """List all store locations"""
    model = StoreLocation
    template_name = 'store_locations.html'
    context_object_name = 'locations'
    
    def get_queryset(self):
        return StoreLocation.objects.filter(is_active=True).order_by('display_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group locations by city
        locations = self.get_queryset()
        locations_by_city = {}
        for location in locations:
            if location.city not in locations_by_city:
                locations_by_city[location.city] = []
            locations_by_city[location.city].append(location)
        
        context['locations_by_city'] = locations_by_city
        return context


def store_location_detail(request, pk):
    """Store location detail page"""
    location = get_object_or_404(StoreLocation, pk=pk, is_active=True)
    
    context = {
        'location': location,
    }
    return render(request, 'store_location_detail.html', context)


# Eye Test Booking
def eye_test_booking(request):
    """Eye test booking page"""
    locations = StoreLocation.objects.filter(
        is_active=True,
        offers_eye_test=True
    ).order_by('display_order')
    
    if request.method == 'POST':
        # Get form data
        location_id = request.POST.get('location')
        booking_date = request.POST.get('booking_date')
        booking_time = request.POST.get('booking_time')
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        customer_email = request.POST.get('customer_email')
        notes = request.POST.get('notes', '')
        
        # Validate
        if not all([location_id, booking_date, booking_time, customer_name, customer_phone, customer_email]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('content:eye_test_booking')
        
        # Create booking
        location = get_object_or_404(StoreLocation, pk=location_id)
        
        booking = EyeTestBooking.objects.create(
            customer=request.user if request.user.is_authenticated else None,
            location=location,
            booking_date=booking_date,
            booking_time=booking_time,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            notes=notes,
            status='pending'
        )
        
        messages.success(request, 'Your eye test appointment has been booked successfully! We will send you a confirmation shortly.')
        
        # Redirect to booking confirmation
        return redirect('content:booking_confirmation', booking_id=booking.id)
    
    context = {
        'locations': locations,
    }
    return render(request, 'eye_test_booking.html', context)


def booking_confirmation(request, booking_id):
    """Booking confirmation page"""
    booking = get_object_or_404(EyeTestBooking, pk=booking_id)
    
    # If user is authenticated, check if booking belongs to them
    if request.user.is_authenticated and booking.customer:
        if booking.customer != request.user:
            messages.error(request, 'You do not have permission to view this booking.')
            return redirect('content:eye_test_booking')
    
    context = {
        'booking': booking,
    }
    return render(request, 'booking_confirmation.html', context)


def cancel_booking(request, booking_id):
    """Cancel an eye test booking"""
    booking = get_object_or_404(EyeTestBooking, pk=booking_id)
    
    # Check permissions
    if request.user.is_authenticated and booking.customer:
        if booking.customer != request.user:
            messages.error(request, 'You do not have permission to cancel this booking.')
            return redirect('catalog:home')
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        
        messages.success(request, 'Your booking has been cancelled successfully.')
        return redirect('catalog:home')
    
    context = {
        'booking': booking,
    }
    return render(request, 'cancel_booking.html', context)


# User Bookings
def my_bookings(request):
    """View user's eye test bookings"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to view your bookings.')
        return redirect('users:login')
    
    bookings = EyeTestBooking.objects.filter(
        customer=request.user
    ).order_by('-booking_date', '-booking_time')
    
    # Separate upcoming and past bookings
    today = timezone.now().date()
    upcoming_bookings = bookings.filter(booking_date__gte=today).exclude(status='cancelled')
    past_bookings = bookings.filter(booking_date__lt=today) | bookings.filter(status='cancelled')
    
    context = {
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
    }
    return render(request, 'my_bookings.html', context)


# AJAX Endpoints
def get_available_times(request):
    """Get available time slots for a specific location and date"""
    location_id = request.GET.get('location_id')
    date_str = request.GET.get('date')
    
    if not location_id or not date_str:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        location = StoreLocation.objects.get(pk=location_id)
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (StoreLocation.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid parameters'}, status=400)
    
    # Get day of week
    day_name = booking_date.strftime('%A').lower()
    
    # Get operating hours for this day
    operating_hours = location.operating_hours.get(day_name, '')
    
    if not operating_hours:
        return JsonResponse({'available_times': []})
    
    # Parse operating hours (format: "9:00-18:00")
    try:
        start_time_str, end_time_str = operating_hours.split('-')
        start_hour = int(start_time_str.split(':')[0])
        end_hour = int(end_time_str.split(':')[0])
    except:
        return JsonResponse({'available_times': []})
    
    # Generate time slots (hourly)
    available_times = []
    for hour in range(start_hour, end_hour):
        time_str = f"{hour:02d}:00"
        
        # Check if this time slot is already booked
        existing_bookings = EyeTestBooking.objects.filter(
            location=location,
            booking_date=booking_date,
            booking_time=time_str,
            status__in=['pending', 'confirmed']
        ).count()
        
        if existing_bookings == 0:
            available_times.append(time_str)
    
    return JsonResponse({'available_times': available_times})


def get_location_details(request):
    """Get location details via AJAX"""
    location_id = request.GET.get('location_id')
    
    if not location_id:
        return JsonResponse({'error': 'Missing location_id'}, status=400)
    
    try:
        location = StoreLocation.objects.get(pk=location_id, is_active=True)
        
        data = {
            'id': location.id,
            'name': location.name,
            'address': f"{location.address_line1}, {location.city}",
            'phone': location.phone,
            'email': location.email,
            'operating_hours': location.operating_hours,
            'google_maps_url': location.google_maps_url,
            'offers_eye_test': location.offers_eye_test,
        }
        
        return JsonResponse(data)
    except StoreLocation.DoesNotExist:
        return JsonResponse({'error': 'Location not found'}, status=404)


# Banner Management (for rendering)
def get_active_banners(banner_type='homepage', placement='main_slider'):
    """Helper function to get active banners"""
    now = timezone.now()
    
    banners = Banner.objects.filter(
        banner_type=banner_type,
        placement=placement,
        is_active=True
    ).filter(
        models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
    ).order_by('display_order')
    
    return banners


# Newsletter Subscription (optional)
def newsletter_subscribe(request):
    """Newsletter subscription handler"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'})
        
        # TODO: Save to newsletter subscription table or send to email service
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for subscribing to our newsletter!'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


# # Terms & Privacy
# def terms_and_conditions(request):
#     """Terms and Conditions page"""
#     try:
#         page = Page.objects.get(slug='terms-and-conditions', is_active=True)
#     except Page.DoesNotExist:
#         page = None
    
#     context = {
#         'page': page,
#     }
#     return render(request, 'terms_and_conditions.html', context)


# def privacy_policy(request):
#     """Privacy Policy page"""
#     try:
#         page = Page.objects.get(slug='privacy-policy', is_active=True)
#     except Page.DoesNotExist:
#         page = None
    
#     context = {
#         'page': page,
#     }
#     return render(request, 'content/privacy_policy.html', context)


# def faq(request):
#     """FAQ page"""
#     try:
#         page = Page.objects.get(slug='faq', is_active=True)
#     except Page.DoesNotExist:
#         page = None
    
#     context = {
#         'page': page,
#     }
#     return render(request, 'content/faq.html', context)