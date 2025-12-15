from django.contrib import admin
from .models import NotificationRequest


@admin.register(NotificationRequest)
class NotificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "variant",
        "requested_power",
        "user",
        "email",
        "notified",
        "active",
        "created_at",
    )

    list_filter = ("notified", "active")
    search_fields = ("email", "variant__product__name")
    readonly_fields = ("created_at", "notified_at")
