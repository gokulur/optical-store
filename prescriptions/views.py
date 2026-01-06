from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from .models import Prescription


@login_required
def prescription_list(request):
    """List all user prescriptions"""
    prescriptions = Prescription.objects.filter(customer=request.user)
    
    # Separate by type
    eyeglass_prescriptions = prescriptions.filter(prescription_type='eyeglasses')
    contact_prescriptions = prescriptions.filter(prescription_type='contact_lenses')
    reading_prescriptions = prescriptions.filter(prescription_type='reading')
    
    context = {
        'eyeglass_prescriptions': eyeglass_prescriptions,
        'contact_prescriptions': contact_prescriptions,
        'reading_prescriptions': reading_prescriptions,
        'all_prescriptions': prescriptions,
    }
    
    return render(request, 'prescriptions/prescription_list.html', context)


@login_required
def prescription_detail(request, prescription_id):
    """View prescription details"""
    prescription = get_object_or_404(
        Prescription,
        id=prescription_id,
        customer=request.user
    )
    
    # Check if prescription is expiring soon (within 30 days)
    expiring_soon = False
    if prescription.expiry_date:
        days_until_expiry = (prescription.expiry_date - timezone.now().date()).days
        if 0 < days_until_expiry <= 30:
            expiring_soon = True
    
    context = {
        'prescription': prescription,
        'expiring_soon': expiring_soon,
    }
    
    return render(request, 'prescriptions/prescription_detail.html', context)


@login_required
def prescription_create(request):
    """Create new prescription"""
    if request.method == 'POST':
        try:
            # Get form data
            prescription_type = request.POST.get('prescription_type')
            prescription_name = request.POST.get('prescription_name', '')
            
            # Right eye
            od_sphere = request.POST.get('od_sphere')
            od_cylinder = request.POST.get('od_cylinder')
            od_axis = request.POST.get('od_axis')
            od_add = request.POST.get('od_add')
            
            # Left eye
            os_sphere = request.POST.get('os_sphere')
            os_cylinder = request.POST.get('os_cylinder')
            os_axis = request.POST.get('os_axis')
            os_add = request.POST.get('os_add')
            
            # PD
            pd = request.POST.get('pd')
            pd_left = request.POST.get('pd_left')
            pd_right = request.POST.get('pd_right')
            
            # Contact lens specific
            od_base_curve = request.POST.get('od_base_curve')
            os_base_curve = request.POST.get('os_base_curve')
            od_diameter = request.POST.get('od_diameter')
            os_diameter = request.POST.get('os_diameter')
            
            # Metadata
            doctor_name = request.POST.get('doctor_name', '')
            clinic_name = request.POST.get('clinic_name', '')
            prescription_date = request.POST.get('prescription_date')
            expiry_date = request.POST.get('expiry_date')
            notes = request.POST.get('notes', '')
            
            is_default = request.POST.get('is_default') == 'on'
            
            # Handle file upload
            prescription_file = request.FILES.get('prescription_file')
            
            # Convert empty strings to None for decimal fields
            def to_decimal(value):
                if value and value.strip():
                    try:
                        return Decimal(value)
                    except (InvalidOperation, ValueError):
                        return None
                return None
            
            def to_int(value):
                if value and value.strip():
                    try:
                        return int(value)
                    except ValueError:
                        return None
                return None
            
            def to_date(value):
                if value and value.strip():
                    try:
                        return datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        return None
                return None
            
            # Create prescription
            prescription = Prescription.objects.create(
                customer=request.user,
                prescription_type=prescription_type,
                prescription_name=prescription_name,
                od_sphere=to_decimal(od_sphere),
                od_cylinder=to_decimal(od_cylinder),
                od_axis=to_int(od_axis),
                od_add=to_decimal(od_add),
                os_sphere=to_decimal(os_sphere),
                os_cylinder=to_decimal(os_cylinder),
                os_axis=to_int(os_axis),
                os_add=to_decimal(os_add),
                pd=to_decimal(pd),
                pd_left=to_decimal(pd_left),
                pd_right=to_decimal(pd_right),
                od_base_curve=to_decimal(od_base_curve),
                os_base_curve=to_decimal(os_base_curve),
                od_diameter=to_decimal(od_diameter),
                os_diameter=to_decimal(os_diameter),
                prescription_file=prescription_file,
                doctor_name=doctor_name,
                clinic_name=clinic_name,
                prescription_date=to_date(prescription_date),
                expiry_date=to_date(expiry_date),
                notes=notes,
                is_default=is_default
            )
            
            # If set as default, unset other defaults
            if is_default:
                Prescription.objects.filter(
                    customer=request.user,
                    prescription_type=prescription_type
                ).exclude(id=prescription.id).update(is_default=False)
            
            messages.success(request, 'Prescription added successfully!')
            return redirect('prescriptions:prescription_detail', prescription_id=prescription.id)
            
        except Exception as e:
            messages.error(request, f'Error creating prescription: {str(e)}')
            return redirect('prescriptions:prescription_create')
    
    context = {
        'prescription_types': Prescription.PRESCRIPTION_TYPES,
    }
    
    return render(request, 'prescriptions/prescription_form.html', context)


@login_required
def prescription_edit(request, prescription_id):
    """Edit existing prescription"""
    prescription = get_object_or_404(
        Prescription,
        id=prescription_id,
        customer=request.user
    )
    
    if request.method == 'POST':
        try:
            # Update fields (same logic as create)
            prescription.prescription_type = request.POST.get('prescription_type')
            prescription.prescription_name = request.POST.get('prescription_name', '')
            
            # Helper function
            def to_decimal(value):
                if value and value.strip():
                    try:
                        return Decimal(value)
                    except (InvalidOperation, ValueError):
                        return None
                return None
            
            def to_int(value):
                if value and value.strip():
                    try:
                        return int(value)
                    except ValueError:
                        return None
                return None
            
            def to_date(value):
                if value and value.strip():
                    try:
                        return datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        return None
                return None
            
            # Right eye
            prescription.od_sphere = to_decimal(request.POST.get('od_sphere'))
            prescription.od_cylinder = to_decimal(request.POST.get('od_cylinder'))
            prescription.od_axis = to_int(request.POST.get('od_axis'))
            prescription.od_add = to_decimal(request.POST.get('od_add'))
            
            # Left eye
            prescription.os_sphere = to_decimal(request.POST.get('os_sphere'))
            prescription.os_cylinder = to_decimal(request.POST.get('os_cylinder'))
            prescription.os_axis = to_int(request.POST.get('os_axis'))
            prescription.os_add = to_decimal(request.POST.get('os_add'))
            
            # PD
            prescription.pd = to_decimal(request.POST.get('pd'))
            prescription.pd_left = to_decimal(request.POST.get('pd_left'))
            prescription.pd_right = to_decimal(request.POST.get('pd_right'))
            
            # Contact lens specific
            prescription.od_base_curve = to_decimal(request.POST.get('od_base_curve'))
            prescription.os_base_curve = to_decimal(request.POST.get('os_base_curve'))
            prescription.od_diameter = to_decimal(request.POST.get('od_diameter'))
            prescription.os_diameter = to_decimal(request.POST.get('os_diameter'))
            
            # Metadata
            prescription.doctor_name = request.POST.get('doctor_name', '')
            prescription.clinic_name = request.POST.get('clinic_name', '')
            prescription.prescription_date = to_date(request.POST.get('prescription_date'))
            prescription.expiry_date = to_date(request.POST.get('expiry_date'))
            prescription.notes = request.POST.get('notes', '')
            
            is_default = request.POST.get('is_default') == 'on'
            prescription.is_default = is_default
            
            # Handle file upload
            if 'prescription_file' in request.FILES:
                prescription.prescription_file = request.FILES['prescription_file']
            
            prescription.save()
            
            # If set as default, unset other defaults
            if is_default:
                Prescription.objects.filter(
                    customer=request.user,
                    prescription_type=prescription.prescription_type
                ).exclude(id=prescription.id).update(is_default=False)
            
            messages.success(request, 'Prescription updated successfully!')
            return redirect('prescriptions:prescription_detail', prescription_id=prescription.id)
            
        except Exception as e:
            messages.error(request, f'Error updating prescription: {str(e)}')
    
    context = {
        'prescription': prescription,
        'prescription_types': Prescription.PRESCRIPTION_TYPES,
        'is_edit': True,
    }
    
    return render(request, 'prescriptions/prescription_form.html', context)


@login_required
@require_POST
def prescription_delete(request, prescription_id):
    """Delete prescription"""
    prescription = get_object_or_404(
        Prescription,
        id=prescription_id,
        customer=request.user
    )
    
    prescription.delete()
    messages.success(request, 'Prescription deleted successfully!')
    
    return redirect('prescriptions:prescription_list')


@login_required
@require_POST
def set_default_prescription(request, prescription_id):
    """Set prescription as default"""
    prescription = get_object_or_404(
        Prescription,
        id=prescription_id,
        customer=request.user
    )
    
    # Unset all other defaults for this type
    Prescription.objects.filter(
        customer=request.user,
        prescription_type=prescription.prescription_type
    ).update(is_default=False)
    
    # Set this as default
    prescription.is_default = True
    prescription.save()
    
    messages.success(request, 'Default prescription updated!')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('prescriptions:prescription_list')


@login_required
@require_GET
def get_prescription_data(request, prescription_id):
    """Get prescription data as JSON (for auto-fill in cart)"""
    prescription = get_object_or_404(
        Prescription,
        id=prescription_id,
        customer=request.user
    )
    
    data = {
        'id': prescription.id,
        'type': prescription.prescription_type,
        'name': prescription.prescription_name,
        'right_eye': {
            'sphere': str(prescription.od_sphere) if prescription.od_sphere else '',
            'cylinder': str(prescription.od_cylinder) if prescription.od_cylinder else '',
            'axis': str(prescription.od_axis) if prescription.od_axis else '',
            'add': str(prescription.od_add) if prescription.od_add else '',
        },
        'left_eye': {
            'sphere': str(prescription.os_sphere) if prescription.os_sphere else '',
            'cylinder': str(prescription.os_cylinder) if prescription.os_cylinder else '',
            'axis': str(prescription.os_axis) if prescription.os_axis else '',
            'add': str(prescription.os_add) if prescription.os_add else '',
        },
        'pd': str(prescription.pd) if prescription.pd else '',
        'pd_left': str(prescription.pd_left) if prescription.pd_left else '',
        'pd_right': str(prescription.pd_right) if prescription.pd_right else '',
        'contact_lens': {
            'od_base_curve': str(prescription.od_base_curve) if prescription.od_base_curve else '',
            'os_base_curve': str(prescription.os_base_curve) if prescription.os_base_curve else '',
            'od_diameter': str(prescription.od_diameter) if prescription.od_diameter else '',
            'os_diameter': str(prescription.os_diameter) if prescription.os_diameter else '',
        }
    }
    
    return JsonResponse(data)


@login_required
@require_GET
def get_default_prescription(request):
    """Get default prescription for a specific type"""
    prescription_type = request.GET.get('type', 'eyeglasses')
    
    prescription = Prescription.objects.filter(
        customer=request.user,
        prescription_type=prescription_type,
        is_default=True
    ).first()
    
    if not prescription:
        return JsonResponse({'error': 'No default prescription found'}, status=404)
    
    data = {
        'id': prescription.id,
        'name': prescription.prescription_name,
        'right_eye': {
            'sphere': str(prescription.od_sphere) if prescription.od_sphere else '',
            'cylinder': str(prescription.od_cylinder) if prescription.od_cylinder else '',
            'axis': str(prescription.od_axis) if prescription.od_axis else '',
            'add': str(prescription.od_add) if prescription.od_add else '',
        },
        'left_eye': {
            'sphere': str(prescription.os_sphere) if prescription.os_sphere else '',
            'cylinder': str(prescription.os_cylinder) if prescription.os_cylinder else '',
            'axis': str(prescription.os_axis) if prescription.os_axis else '',
            'add': str(prescription.os_add) if prescription.os_add else '',
        },
        'pd': str(prescription.pd) if prescription.pd else '',
    }
    
    return JsonResponse(data)


@login_required
def prescription_upload(request):
    """Upload prescription file/image"""
    if request.method == 'POST':
        prescription_file = request.FILES.get('prescription_file')
        prescription_type = request.POST.get('prescription_type', 'eyeglasses')
        notes = request.POST.get('notes', '')
        
        if not prescription_file:
            messages.error(request, 'Please select a file to upload')
            return redirect('prescriptions:prescription_upload')
        
        # Create prescription with just the file
        prescription = Prescription.objects.create(
            customer=request.user,
            prescription_type=prescription_type,
            prescription_file=prescription_file,
            notes=notes,
            prescription_name=f'Uploaded on {timezone.now().strftime("%Y-%m-%d")}'
        )
        
        messages.success(request, 'Prescription uploaded successfully! Our team will review and add the details.')
        return redirect('prescriptions:prescription_detail', prescription_id=prescription.id)
    
    context = {
        'prescription_types': Prescription.PRESCRIPTION_TYPES,
    }
    
    return render(request, 'prescriptions/prescription_upload.html', context)


@login_required
def prescription_history(request):
    """View prescription history/changes"""
    prescriptions = Prescription.objects.filter(
        customer=request.user
    ).order_by('-created_at')
    
    context = {
        'prescriptions': prescriptions,
    }
    
    return render(request, 'prescriptions/prescription_history.html', context)


# Helper function for prescription validation
def validate_prescription_values(prescription_data):
    """Validate prescription values"""
    errors = []
    warnings = []
    
    # Check sphere range
    for eye in ['od', 'os']:
        sphere_key = f'{eye}_sphere'
        if sphere_key in prescription_data and prescription_data[sphere_key]:
            sphere = float(prescription_data[sphere_key])
            if abs(sphere) > 20:
                errors.append(f'{eye.upper()} sphere value seems unusually high')
            elif abs(sphere) > 10:
                warnings.append(f'{eye.upper()} sphere is very high - consider high-index lenses')
    
    # Check cylinder range
    for eye in ['od', 'os']:
        cyl_key = f'{eye}_cylinder'
        if cyl_key in prescription_data and prescription_data[cyl_key]:
            cyl = float(prescription_data[cyl_key])
            if abs(cyl) > 6:
                errors.append(f'{eye.upper()} cylinder value seems unusually high')
    
    # Check axis range
    for eye in ['od', 'os']:
        axis_key = f'{eye}_axis'
        if axis_key in prescription_data and prescription_data[axis_key]:
            axis = int(prescription_data[axis_key])
            if axis < 0 or axis > 180:
                errors.append(f'{eye.upper()} axis must be between 0 and 180')
    
    # Check PD range
    if 'pd' in prescription_data and prescription_data['pd']:
        pd = float(prescription_data['pd'])
        if pd < 50 or pd > 80:
            warnings.append('PD value seems unusual (typical range: 54-74mm)')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }