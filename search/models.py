# search/models.py
from django.db import models
from django.conf import settings


class SearchQuery(models.Model):
    """Track user searches"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='search_queries')
    session_key = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    
    query = models.CharField(max_length=500, db_index=True)
    results_count = models.PositiveIntegerField(default=0)
    
    # Filters applied
    filters_applied = models.JSONField(default=dict, blank=True)
    
    clicked_product_id = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['query']),
            models.Index(fields=['-created_at']),
        ]


class PopularSearch(models.Model):
    """Curated popular searches for autocomplete"""
    keyword = models.CharField(max_length=200, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'popular_searches'
        ordering = ['display_order']