from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re

User = get_user_model()

class RegisterForm(forms.Form):
    first_name = forms.CharField(min_length=2, max_length=50, required=True)
    last_name = forms.CharField(min_length=2, max_length=50, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True)
    terms = forms.BooleanField(required=True)

    def clean_first_name(self):
        name = self.cleaned_data["first_name"].strip()
        if not name.isalpha():
            raise ValidationError("First name must contain only letters")
        return name.title()

    def clean_last_name(self):
        name = self.cleaned_data["last_name"].strip()
        if not name.isalpha():
            raise ValidationError("Last name must contain only letters")
        return name.title()

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already registered")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone and not re.match(r"^\+?[0-9]{8,15}$", phone):
            raise ValidationError("Enter valid phone number")
        return phone

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)

        if not re.search(r"[A-Z]", password):
            raise ValidationError("Add at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Add at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            raise ValidationError("Add at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError("Add at least one special character")

        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match")
        return cleaned
