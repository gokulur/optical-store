from django.db import models
from django.conf import settings
from catalog.models import ProductVariant, ContactLensPower


class NotificationRequest(models.Model):
    """
    User requests notification when a product / power comes back in stock
    """

    # Logged-in user (optional)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_requests"
    )

    # For guest users
    email = models.EmailField(null=True, blank=True)

    # What product variant they want
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="notification_requests"
    )

    # Optional power (for contact lenses / powered lenses)
    requested_power = models.ForeignKey(
        ContactLensPower,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Status flags
    notified = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["variant", "requested_power", "notified"]),
        ]
        verbose_name = "Notification Request"
        verbose_name_plural = "Notification Requests"

    def __str__(self):
        target = self.email if self.email else self.user
        return f"Notify {target} for {self.variant}"
