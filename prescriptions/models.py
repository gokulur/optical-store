# prescriptions/models.py
from django.db import models
from django.conf import settings


class Prescription(models.Model):
    """Customer prescription records"""
    PRESCRIPTION_TYPES = [
        ('eyeglasses', 'Eyeglasses'),
        ('contact_lenses', 'Contact Lenses'),
        ('reading', 'Reading Glasses'),
    ]
    
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prescriptions')
    
    prescription_type = models.CharField(max_length=50, choices=PRESCRIPTION_TYPES)
    prescription_name = models.CharField(max_length=200, blank=True)  # User-friendly name
    
    # Right Eye (OD)
    od_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    od_cylinder = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    od_axis = models.IntegerField(null=True, blank=True)
    od_add = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)  # For progressives
    
    # Left Eye (OS)
    os_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    os_cylinder = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    os_axis = models.IntegerField(null=True, blank=True)
    os_add = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Pupillary Distance
    pd = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pd_left = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pd_right = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    
    # For contact lenses
    od_base_curve = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    os_base_curve = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    od_diameter = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    os_diameter = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Metadata
    prescription_file = models.FileField(upload_to='prescriptions/', null=True, blank=True)
    doctor_name = models.CharField(max_length=200, blank=True)
    clinic_name = models.CharField(max_length=200, blank=True)
    prescription_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_prescriptions')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'prescriptions'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['customer', 'is_default']),
        ]