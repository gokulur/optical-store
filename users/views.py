from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


# ==================== REGISTER ====================

def user_register(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'register.html')

        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html')

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return render(request, 'register.html')

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            phone=request.POST.get('phone', ''),
            user_type='customer'
        )

        login(request, user)
        messages.success(request, 'Account created successfully!')
        return redirect_after_login(user)

    return render(request, 'register.html')


# ==================== LOGIN ====================

def user_login(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

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
            return redirect_after_login(user)

        messages.error(request, 'Invalid email or password')

    return render(request, 'login.html')



# ==================== REDIRECT LOGIC ====================

def redirect_after_login(user):
    """
    Admin / Staff → admin pages
    Normal user → user dashboard
    """
    if user.is_superuser or user.user_type == 'admin':
        return redirect('/adminpanel/')
    elif user.is_staff or user.user_type == 'staff':
        return redirect('/adminpanel/')
    else:
        return redirect('users:dashboard')


# ==================== LOGOUT ====================

@login_required
def user_logout(request):
    logout(request)
    return redirect('users:login')
