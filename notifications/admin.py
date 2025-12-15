from django.contrib import admin
from .models import NotificationRequest

@admin.register(NotificationRequest)
class NotificationRequestAdmin(admin.ModelAdmin):
    list_display = ("variant", "requested_power", "notified", "created_at")
    list_filter = ("notified",)
