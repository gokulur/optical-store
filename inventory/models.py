from django.db import models
from catalog.models import ProductVariant, ContactLensPower

class Stock(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="stocks")
    power = models.ForeignKey(ContactLensPower, on_delete=models.CASCADE, null=True, blank=True)

    quantity = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "power"], name="unique_stock_variant_power")
        ]
        indexes = [
            models.Index(fields=["variant", "power"]),
        ]

    def available(self):
        return max(self.quantity - self.reserved, 0)

    def __str__(self):
        return f"{self.variant} [{self.power}] - {self.available()}"
