from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count
from datetime import datetime

from .models import User, CustomerProfile, Address


# ==================== REGISTER ====================
def user_register(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect_after_login(request.user)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone = request.POST.get('phone', '')
        
        # Validation
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'users/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/register.html')
        
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return render(request, 'users/register.html')
        
        # Create user
        username = email.split('@')[0]  # Use email prefix as username
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            user_type='customer'
        )
        
        # Create customer profile
        CustomerProfile.objects.create(user=user)
        
        # Login user
        login(request, user)
        messages.success(request, 'Account created successfully! Welcome to our store.')
        
        return redirect_after_login(user)
    
    return render(request, 'users/register.html')


# ==================== LOGIN ====================
def user_login(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect_after_login(request.user)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(
                request,
                username=user_obj.username,
                password=password
            )
        except User.DoesNotExist:
            user = None
        
        if user:
            login(request, user)
            
            # Handle remember me
            if not remember_me:
                request.session.set_expiry(0)  # Session expires on browser close
            
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            
            # Redirect to next parameter if exists
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect_after_login(user)
        
        messages.error(request, 'Invalid email or password')
    
    return render(request, 'users/login.html')


# ==================== REDIRECT LOGIC ====================
def redirect_after_login(user):
    """Redirect based on user type"""
    if user.is_superuser or user.user_type == 'admin':
        return redirect('/admin/')
    elif user.is_staff or user.user_type == 'staff':
        return redirect('/admin/')
    else:
        return redirect('users:dashboard')


# ==================== LOGOUT ====================
@login_required
def user_logout(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')


# ==================== DASHBOARD ====================
@login_required
def dashboard(request):
    """User dashboard"""
    user = request.user
    
    # Get recent orders (you'll need to import Order model)
    # recent_orders = Order.objects.filter(customer=user).order_by('-created_at')[:5]
    recent_orders = []  # Placeholder
    
    # Get customer profile
    try:
        profile = user.customer_profile
    except:
        profile = CustomerProfile.objects.create(user=user)
    
    # Get statistics
    # order_stats = Order.objects.filter(customer=user).aggregate(
    #     total_orders=Count('id'),
    #     total_spent=Sum('total_amount')
    # )
    order_stats = {'total_orders': 0, 'total_spent': 0}  # Placeholder
    
    # Get saved addresses
    addresses = user.addresses.all()[:3]
    
    # Get prescriptions count
    prescriptions_count = user.prescriptions.count()
    
    # Get reviews count
    reviews_count = user.reviews.count()
    
    context = {
        'user': user,
        'profile': profile,
        'recent_orders': recent_orders,
        'order_stats': order_stats,
        'addresses': addresses,
        'prescriptions_count': prescriptions_count,
        'reviews_count': reviews_count,
    }
    
    return render(request, 'users/dashboard.html', context)


# ==================== PROFILE ====================
@login_required
def profile_view(request):
    """View/edit profile"""
    user = request.user
    
    try:
        profile = user.customer_profile
    except:
        profile = CustomerProfile.objects.create(user=user)
    
    if request.method == 'POST':
        # Update user fields
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.phone = request.POST.get('phone', '')
        user.city = request.POST.get('city', '')
        user.state = request.POST.get('state', '')
        user.country = request.POST.get('country', 'Qatar')
        user.preferred_language = request.POST.get('preferred_language', 'en')
        user.preferred_currency = request.POST.get('preferred_currency', 'QAR')
        user.email_notifications = request.POST.get('email_notifications') == 'on'
        user.sms_notifications = request.POST.get('sms_notifications') == 'on'
        user.save()
        
        # Update profile fields
        date_of_birth = request.POST.get('date_of_birth')
        if date_of_birth:
            try:
                profile.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except:
                pass
        
        profile.gender = request.POST.get('gender', '')
        profile.preferred_contact_method = request.POST.get('preferred_contact_method', 'email')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('users:profile')
    
    context = {
        'user': user,
        'profile': profile,
    }
    
    return render(request, 'users/profile.html', context)


# ==================== CHANGE PASSWORD ====================
@login_required
def change_password(request):
    """Change password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('users:change_password')
        
        # Check new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('users:change_password')
        
        # Validate new password
        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('users:change_password')
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Keep user logged in
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('users:dashboard')
    
    return render(request, 'users/change_password.html')


# ==================== ADDRESSES ====================
@login_required
def address_list(request):
    """List all addresses"""
    addresses = request.user.addresses.all()
    
    context = {
        'addresses': addresses,
    }
    
    return render(request, 'users/address_list.html', context)


@login_required
def address_create(request):
    """Create new address"""
    if request.method == 'POST':
        try:
            # Get form data
            address_type = request.POST.get('address_type', 'both')
            full_name = request.POST.get('full_name')
            phone = request.POST.get('phone')
            address_line1 = request.POST.get('address_line1')
            address_line2 = request.POST.get('address_line2', '')
            city = request.POST.get('city')
            state = request.POST.get('state', '')
            country = request.POST.get('country', 'Qatar')
            postal_code = request.POST.get('postal_code', '')
            is_default_shipping = request.POST.get('is_default_shipping') == 'on'
            is_default_billing = request.POST.get('is_default_billing') == 'on'
            
            # Create address
            address = Address.objects.create(
                user=request.user,
                address_type=address_type,
                full_name=full_name,
                phone=phone,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                country=country,
                postal_code=postal_code,
                is_default_shipping=is_default_shipping,
                is_default_billing=is_default_billing
            )
            
            # Unset other defaults if this is set as default
            if is_default_shipping:
                Address.objects.filter(
                    user=request.user
                ).exclude(id=address.id).update(is_default_shipping=False)
            
            if is_default_billing:
                Address.objects.filter(
                    user=request.user
                ).exclude(id=address.id).update(is_default_billing=False)
            
            messages.success(request, 'Address added successfully!')
            return redirect('users:address_list')
            
        except Exception as e:
            messages.error(request, f'Error adding address: {str(e)}')
    
    context = {
        'is_edit': False,
    }
    
    return render(request, 'users/address_form.html', context)


@login_required
def address_edit(request, address_id):
    """Edit existing address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        try:
            address.address_type = request.POST.get('address_type', 'both')
            address.full_name = request.POST.get('full_name')
            address.phone = request.POST.get('phone')
            address.address_line1 = request.POST.get('address_line1')
            address.address_line2 = request.POST.get('address_line2', '')
            address.city = request.POST.get('city')
            address.state = request.POST.get('state', '')
            address.country = request.POST.get('country', 'Qatar')
            address.postal_code = request.POST.get('postal_code', '')
            
            is_default_shipping = request.POST.get('is_default_shipping') == 'on'
            is_default_billing = request.POST.get('is_default_billing') == 'on'
            
            address.is_default_shipping = is_default_shipping
            address.is_default_billing = is_default_billing
            address.save()
            
            # Unset other defaults
            if is_default_shipping:
                Address.objects.filter(
                    user=request.user
                ).exclude(id=address.id).update(is_default_shipping=False)
            
            if is_default_billing:
                Address.objects.filter(
                    user=request.user
                ).exclude(id=address.id).update(is_default_billing=False)
            
            messages.success(request, 'Address updated successfully!')
            return redirect('users:address_list')
            
        except Exception as e:
            messages.error(request, f'Error updating address: {str(e)}')
    
    context = {
        'address': address,
        'is_edit': True,
    }
    
    return render(request, 'users/address_form.html', context)


@login_required
@require_POST
def address_delete(request, address_id):
    """Delete address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    
    messages.success(request, 'Address deleted successfully!')
    return redirect('users:address_list')


@login_required
@require_POST
def set_default_address(request, address_id):
    """Set address as default"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address_type = request.POST.get('type', 'shipping')
    
    if address_type == 'shipping':
        Address.objects.filter(user=request.user).update(is_default_shipping=False)
        address.is_default_shipping = True
    elif address_type == 'billing':
        Address.objects.filter(user=request.user).update(is_default_billing=False)
        address.is_default_billing = True
    
    address.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Default address updated!')
    return redirect('users:address_list')


# ==================== ACCOUNT SETTINGS ====================
@login_required
def account_settings(request):
    """Account settings page"""
    user = request.user
    
    try:
        profile = user.customer_profile
    except:
        profile = CustomerProfile.objects.create(user=user)
    
    context = {
        'user': user,
        'profile': profile,
    }
    
    return render(request, 'users/settings.html', context)


# ==================== FORGOT PASSWORD ====================
def forgot_password(request):
    """Forgot password - send reset email"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            # TODO: Send password reset email
            # For now, just show success message
            messages.success(request, 'Password reset instructions have been sent to your email.')
            return redirect('users:login')
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
    
    return render(request, 'users/forgot_password.html')


# ==================== DELETE ACCOUNT ====================
@login_required
def delete_account(request):
    """Delete user account"""
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')
        
        if confirm != 'DELETE':
            messages.error(request, 'Please type DELETE to confirm.')
            return redirect('users:delete_account')
        
        if not request.user.check_password(password):
            messages.error(request, 'Incorrect password.')
            return redirect('users:delete_account')
        
        # Delete user account
        user = request.user
        logout(request)
        user.delete()
        
        messages.success(request, 'Your account has been deleted successfully.')
        return redirect('catalog:home')
    
    return render(request, 'users/delete_account.html')