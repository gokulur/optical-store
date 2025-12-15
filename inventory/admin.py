from django.contrib import admin
from .models import Stock

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("variant", "power", "quantity", "reserved", "last_updated")
    list_filter = ("variant__product",)
    search_fields = ("variant__product__name",)
