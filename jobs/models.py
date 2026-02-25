from django.db import models
from django.utils import timezone
from django.conf import settings


class JobOrder(models.Model):
    """
    Represents an in-store OR online job/order for optical work
    (e.g. frame fitting, lens cutting, prescription fulfilment).
    Created by admin/staff; customers can track progress.
    """

    # ── Status flow ──────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('received',    'Job Received'),
        ('processing',  'In Processing'),
        ('lens_order',  'Lens Ordered'),
        ('fitting',     'Frame Fitting'),
        ('qa',          'Quality Check'),
        ('ready',       'Ready for Pickup / Dispatch'),
        ('dispatched',  'Dispatched'),
        ('delivered',   'Delivered / Collected'),
        ('on_hold',     'On Hold'),
        ('cancelled',   'Cancelled'),
    ]

    JOB_TYPE_CHOICES = [
        ('in_store',    'In-Store Job'),
        ('online',      'Online Order'),
        ('repair',      'Repair / Adjustment'),
        ('lens_only',   'Lens Replacement Only'),
        ('contact',     'Contact Lens Order'),
    ]

    SOURCE_CHOICES = [
        ('walk_in',     'Walk-In'),
        ('phone',       'Phone'),
        ('website',     'Website'),
        ('whatsapp',    'WhatsApp'),
        ('referral',    'Referral'),
    ]

    PRIORITY_CHOICES = [
        ('normal',  'Normal'),
        ('urgent',  'Urgent'),
        ('express', 'Express (Same Day)'),
    ]

    # ── Core fields ──────────────────────────────────────────────────────
    job_number    = models.CharField(max_length=30, unique=True, db_index=True)
    job_type      = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='in_store')
    source        = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='walk_in')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    priority      = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')

    # ── Customer info ────────────────────────────────────────────────────
    customer      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='job_orders'
    )
    customer_name  = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30)
    customer_email = models.EmailField(blank=True)

    # ── Linked order (optional) ──────────────────────────────────────────
    linked_order   = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='job_orders'
    )

    # ── Prescription ─────────────────────────────────────────────────────
    # Right Eye
    re_sphere    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    re_cylinder  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    re_axis      = models.IntegerField(null=True, blank=True)
    re_add       = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    # Left Eye
    le_sphere    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    le_cylinder  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    le_axis      = models.IntegerField(null=True, blank=True)
    le_add       = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    # PD
    pd_distance  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pd_near      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ── Product / lens details ───────────────────────────────────────────
    frame_description = models.CharField(max_length=255, blank=True)
    lens_brand        = models.CharField(max_length=100, blank=True)
    lens_type         = models.CharField(max_length=100, blank=True)
    lens_index        = models.CharField(max_length=20, blank=True)
    lens_coating      = models.CharField(max_length=100, blank=True)
    lens_color        = models.CharField(max_length=80, blank=True)

    # ── Financials ───────────────────────────────────────────────────────
    frame_price  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lens_price   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    addon_price  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_due  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid      = models.BooleanField(default=False)

    # ── Dates ────────────────────────────────────────────────────────────
    promised_date    = models.DateField(null=True, blank=True)
    completed_date   = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    # ── Staff ────────────────────────────────────────────────────────────
    assigned_to      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_jobs'
    )
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_jobs'
    )

    # ── Notes ────────────────────────────────────────────────────────────
    internal_notes   = models.TextField(blank=True)
    customer_notes   = models.TextField(blank=True)

    # ── Prescription file upload ─────────────────────────────────────────
    prescription_file = models.FileField(
        upload_to='jobs/prescriptions/%Y/%m/',
        null=True, blank=True
    )

    class Meta:
        db_table  = 'jobs_job_orders'
        ordering  = ['-created_at']
        verbose_name = 'Job Order'
        verbose_name_plural = 'Job Orders'

    def __str__(self):
        return f"Job #{self.job_number} — {self.customer_name}"

    def save(self, *args, **kwargs):
        # Auto-generate job number
        if not self.job_number:
            last = JobOrder.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.job_number = f"JOB{timezone.now().year}{str(next_id).zfill(5)}"
        # Auto balance
        self.balance_due = self.total_amount - self.advance_paid
        if self.balance_due <= 0:
            self.is_paid = True
        super().save(*args, **kwargs)

    @property
    def status_display_class(self):
        mapping = {
            'received':   'warning',
            'processing': 'info',
            'lens_order': 'primary',
            'fitting':    'info',
            'qa':         'primary',
            'ready':      'success',
            'dispatched': 'success',
            'delivered':  'success',
            'on_hold':    'secondary',
            'cancelled':  'danger',
        }
        return mapping.get(self.status, 'secondary')

    @property
    def progress_percent(self):
        steps = ['received', 'processing', 'lens_order', 'fitting', 'qa', 'ready', 'dispatched', 'delivered']
        try:
            idx = steps.index(self.status)
            return int((idx / (len(steps) - 1)) * 100)
        except ValueError:
            return 0


class JobStatusHistory(models.Model):
    """Audit trail of every status change on a job."""
    job         = models.ForeignKey(JobOrder, on_delete=models.CASCADE, related_name='history')
    old_status  = models.CharField(max_length=20, blank=True)
    new_status  = models.CharField(max_length=20)
    note        = models.TextField(blank=True)
    changed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'jobs_status_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job.job_number}: {self.old_status} → {self.new_status}"


class JobDocument(models.Model):
    """Photos, receipts, or any file attached to a job."""
    DOC_TYPES = [
        ('prescription', 'Prescription'),
        ('photo',        'Photo'),
        ('receipt',      'Receipt'),
        ('other',        'Other'),
    ]
    job         = models.ForeignKey(JobOrder, on_delete=models.CASCADE, related_name='documents')
    doc_type    = models.CharField(max_length=20, choices=DOC_TYPES, default='other')
    file        = models.FileField(upload_to='jobs/documents/%Y/%m/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'jobs_documents'