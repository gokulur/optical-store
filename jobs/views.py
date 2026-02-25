
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from jobs.models import JobOrder

PROGRESS_STEPS = [
    ('received',   'Received'),
    ('processing', 'Processing'),
    ('lens_order', 'Lens Ordered'),
    ('fitting',    'Fitting'),
    ('qa',         'QA Check'),
    ('ready',      'Ready'),
    ('dispatched', 'Dispatched'),
    ('delivered',  'Delivered'),
]

def _build_progress_steps(job):
    step_keys = [k for k, _ in PROGRESS_STEPS]
    current_idx = step_keys.index(job.status) if job.status in step_keys else -1
    steps = []
    for i, (key, label) in enumerate(PROGRESS_STEPS):
        if i < current_idx:
            state = 'done'
        elif i == current_idx:
            state = 'active'
        else:
            state = 'pending'
        steps.append((key, label, state))
    return steps

def job_track(request):
    job = None
    error = None
    if request.method == 'POST':
        job_number = request.POST.get('job_number', '').strip().upper()
        phone      = request.POST.get('phone', '').strip()
        if job_number and phone:
            try:
                job = JobOrder.objects.prefetch_related('history').get(
                    job_number=job_number,
                    customer_phone__icontains=phone[-6:]
                )
            except JobOrder.DoesNotExist:
                error = 'No job found with that number and phone. Please check your details.'
        else:
            error = 'Please enter both your job number and phone number.'
    history = job.history.order_by('created_at') if job else []
    return render(request, 'track.html', {
        'job': job, 'error': error,
        'history': history, 'steps_data': PROGRESS_STEPS,
    })

@login_required
def my_jobs(request):
    jobs = JobOrder.objects.filter(
        Q(customer=request.user) | Q(customer_email=request.user.email)
    ).order_by('-created_at')
    return render(request, 'my_jobs.html', {'jobs': jobs})

@login_required
def job_detail_user(request, job_number):
    job = get_object_or_404(
        JobOrder.objects.prefetch_related('history', 'documents'),
        job_number=job_number
    )
    is_owner = (
        (job.customer and job.customer == request.user) or
        job.customer_email == request.user.email
    )
    if not is_owner:
        from django.http import Http404
        raise Http404
    history = job.history.order_by('created_at')
    progress_steps = _build_progress_steps(job)
    return render(request, 'detail.html', {
        'job': job, 'history': history, 'progress_steps': progress_steps,
    })