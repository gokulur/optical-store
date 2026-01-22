# users/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import re

User = get_user_model()


class RegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        min_length=2,
        required=True
    )

    last_name = forms.CharField(
        max_length=50,
        min_length=2,
        required=True
    )

    email = forms.EmailField(required=True)

    phone = forms.CharField(required=False)

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True
    )

    password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        required=True
    )

    terms = forms.BooleanField(
        required=True,
        error_messages={"required": "You must accept Terms & Conditions"}
    )

    # ---------- Field validations ----------

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
        validate_email(email)

        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")

        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if phone:
            phone = phone.strip()

            # International professional regex
            if not re.match(r"^\+?[1-9]\d{7,14}$", phone):
                raise ValidationError("Enter a valid international phone number")

        return phone

    def clean_password(self):
        password = self.cleaned_data.get("password")

        # Django built-in validators (length, common passwords, numeric, etc.)
        validate_password(password)

        # Extra security rule
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter")

        if not re.search(r"[0-9]", password):
            raise ValidationError("Password must contain at least one number")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError("Password must contain at least one special character")

        return password

    def clean(self):
        cleaned = super().clean()

        password = cleaned.get("password")
        confirm = cleaned.get("password_confirm")

        if password and confirm and password != confirm:
            self.add_error("password_confirm", "Passwords do not match")

        return cleaned
