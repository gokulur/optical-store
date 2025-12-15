from django.db import models
from django.conf import settings

class Prescription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prescriptions"
    )

    left_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    left_cyl = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_cyl = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    left_axis = models.IntegerField(null=True, blank=True)
    right_axis = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to="prescriptions/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription #{self.id} for {self.user}"
