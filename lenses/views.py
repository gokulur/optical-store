from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from decimal import Decimal
import json

from .models import (
    LensCategory, LensOption, LensAddOn, 
    LensOptionAddOn, SunglassLensOption
)


# Lens Categories View
def lens_categories_view(request):
    """Display all lens categories with their options"""
    categories = LensCategory.objects.filter(is_active=True).prefetch_related(
        'lens_options'
    )
    
    context = {
        'categories': categories,
    }
    return render(request, 'lenses/categories.html', context)


# Get Lens Options by Category (AJAX)
@require_GET
def get_lens_options_by_category(request):
    """Get lens options for a specific category"""
    category_type = request.GET.get('category_type')
    
    if not category_type:
        return JsonResponse({'error': 'Category type required'}, status=400)
    
    try:
        category = LensCategory.objects.get(
            category_type=category_type,
            is_active=True
        )
        
        lens_options = category.lens_options.filter(is_active=True)
        
        options_data = []
        for option in lens_options:
            # Get available add-ons with pricing
            addons = []
            for addon_link in option.available_addons.all():
                addons.append({
                    'id': addon_link.addon.id,
                    'name': addon_link.addon.name,
                    'addon_type': addon_link.addon.addon_type,
                    'price': str(addon_link.price),
                    'description': addon_link.addon.description,
                })
            
            options_data.append({
                'id': option.id,
                'name': option.name,
                'code': option.code,
                'description': option.description,
                'base_price': str(option.base_price),
                'lens_index': str(option.lens_index),
                'features': option.features,
                'min_sphere_power': str(option.min_sphere_power) if option.min_sphere_power else None,
                'max_sphere_power': str(option.max_sphere_power) if option.max_sphere_power else None,
                'min_cylinder_power': str(option.min_cylinder_power) if option.min_cylinder_power else None,
                'max_cylinder_power': str(option.max_cylinder_power) if option.max_cylinder_power else None,
                'available_reading_powers': option.available_reading_powers,
                'available_addons': addons,
                'is_premium': option.is_premium,
            })
        
        return JsonResponse({
            'success': True,
            'category': {
                'name': category.name,
                'type': category.category_type,
            },
            'lens_options': options_data
        })
        
    except LensCategory.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Get Lens Option Details (AJAX)
@require_GET
def get_lens_option_details(request):
    """Get detailed information for a specific lens option"""
    option_id = request.GET.get('option_id')
    
    if not option_id:
        return JsonResponse({'error': 'Option ID required'}, status=400)
    
    try:
        option = LensOption.objects.get(id=option_id, is_active=True)
        
        # Get available add-ons
        addons = []
        for addon_link in option.available_addons.all():
            addons.append({
                'id': addon_link.addon.id,
                'name': addon_link.addon.name,
                'addon_type': addon_link.addon.addon_type,
                'price': str(addon_link.price),
                'description': addon_link.addon.description,
                'display_order': addon_link.display_order,
            })
        
        data = {
            'id': option.id,
            'name': option.name,
            'code': option.code,
            'description': option.description,
            'base_price': str(option.base_price),
            'lens_index': str(option.lens_index),
            'material': option.material,
            'features': option.features,
            'category': {
                'name': option.category.name,
                'type': option.category.category_type,
            },
            'power_range': {
                'min_sphere': str(option.min_sphere_power) if option.min_sphere_power else None,
                'max_sphere': str(option.max_sphere_power) if option.max_sphere_power else None,
                'min_cylinder': str(option.min_cylinder_power) if option.min_cylinder_power else None,
                'max_cylinder': str(option.max_cylinder_power) if option.max_cylinder_power else None,
            },
            'available_reading_powers': option.available_reading_powers,
            'available_addons': addons,
            'is_premium': option.is_premium,
        }
        
        return JsonResponse({
            'success': True,
            'lens_option': data
        })
        
    except LensOption.DoesNotExist:
        return JsonResponse({'error': 'Lens option not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Calculate Lens Price (AJAX)
@require_GET
def calculate_lens_price(request):
    """Calculate total lens price including add-ons"""
    option_id = request.GET.get('option_id')
    addon_ids = request.GET.getlist('addon_ids[]')
    
    if not option_id:
        return JsonResponse({'error': 'Option ID required'}, status=400)
    
    try:
        option = LensOption.objects.get(id=option_id, is_active=True)
        
        # Base price
        total_price = option.base_price
        
        # Add-on prices
        addon_details = []
        if addon_ids:
            for addon_id in addon_ids:
                addon_link = LensOptionAddOn.objects.filter(
                    lens_option=option,
                    addon_id=addon_id
                ).first()
                
                if addon_link:
                    total_price += addon_link.price
                    addon_details.append({
                        'id': addon_link.addon.id,
                        'name': addon_link.addon.name,
                        'price': str(addon_link.price),
                    })
        
        return JsonResponse({
            'success': True,
            'base_price': str(option.base_price),
            'addon_total': str(sum(Decimal(a['price']) for a in addon_details)),
            'total_price': str(total_price),
            'addons': addon_details,
        })
        
    except LensOption.DoesNotExist:
        return JsonResponse({'error': 'Lens option not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Validate Prescription (AJAX)
@require_GET
def validate_prescription(request):
    """Validate prescription values against lens option power ranges"""
    option_id = request.GET.get('option_id')
    
    # Prescription values
    right_sph = request.GET.get('right_sph')
    right_cyl = request.GET.get('right_cyl')
    left_sph = request.GET.get('left_sph')
    left_cyl = request.GET.get('left_cyl')
    
    if not option_id:
        return JsonResponse({'error': 'Option ID required'}, status=400)
    
    try:
        option = LensOption.objects.get(id=option_id, is_active=True)
        
        errors = []
        warnings = []
        
        # Convert to Decimal for comparison
        def to_decimal(value):
            if value and value != '':
                return Decimal(str(value))
            return None
        
        r_sph = to_decimal(right_sph)
        r_cyl = to_decimal(right_cyl)
        l_sph = to_decimal(left_sph)
        l_cyl = to_decimal(left_cyl)
        
        # Validate sphere powers
        if option.min_sphere_power and option.max_sphere_power:
            if r_sph and (r_sph < option.min_sphere_power or r_sph > option.max_sphere_power):
                errors.append(f"Right eye sphere power {r_sph} is outside range ({option.min_sphere_power} to {option.max_sphere_power})")
            
            if l_sph and (l_sph < option.min_sphere_power or l_sph > option.max_sphere_power):
                errors.append(f"Left eye sphere power {l_sph} is outside range ({option.min_sphere_power} to {option.max_sphere_power})")
        
        # Validate cylinder powers
        if option.min_cylinder_power and option.max_cylinder_power:
            if r_cyl and (r_cyl < option.min_cylinder_power or r_cyl > option.max_cylinder_power):
                errors.append(f"Right eye cylinder power {r_cyl} is outside range ({option.min_cylinder_power} to {option.max_cylinder_power})")
            
            if l_cyl and (l_cyl < option.min_cylinder_power or l_cyl > option.max_cylinder_power):
                errors.append(f"Left eye cylinder power {l_cyl} is outside range ({option.min_cylinder_power} to {option.max_cylinder_power})")
        
        # Recommendations
        if r_sph and l_sph:
            if abs(r_sph) > 6 or abs(l_sph) > 6:
                warnings.append("High prescription detected. Consider upgrading to high-index lenses (1.67 or 1.74) for thinner, lighter lenses.")
        
        return JsonResponse({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'power_range': {
                'sphere': f"{option.min_sphere_power} to {option.max_sphere_power}",
                'cylinder': f"{option.min_cylinder_power} to {option.max_cylinder_power}",
            }
        })
        
    except LensOption.DoesNotExist:
        return JsonResponse({'error': 'Lens option not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Get Sunglass Lens Options (AJAX)
@require_GET
def get_sunglass_lens_options(request):
    """Get available sunglass lens options"""
    with_prescription = request.GET.get('with_prescription', 'false') == 'true'
    
    options = SunglassLensOption.objects.filter(is_active=True)
    
    options_data = []
    for option in options:
        options_data.append({
            'id': option.id,
            'name': option.name,
            'lens_type': option.lens_type,
            'base_price': str(option.base_price),
            'lens_index': str(option.lens_index),
            'features': option.features,
        })
    
    return JsonResponse({
        'success': True,
        'lens_options': options_data
    })


# Lens Comparison View
def lens_comparison_view(request):
    """Compare different lens options"""
    option_ids = request.GET.getlist('option_ids')
    
    if not option_ids:
        # Show all options for selection
        categories = LensCategory.objects.filter(is_active=True).prefetch_related('lens_options')
        context = {
            'categories': categories,
        }
        return render(request, 'lenses/comparison_select.html', context)
    
    # Get selected options
    options = LensOption.objects.filter(
        id__in=option_ids,
        is_active=True
    ).prefetch_related('available_addons')
    
    context = {
        'options': options,
    }
    return render(request, 'lenses/comparison.html', context)


# Lens Guide/Education Page
def lens_guide_view(request):
    """Educational page about lens types and features"""
    categories = LensCategory.objects.filter(is_active=True)
    
    context = {
        'categories': categories,
    }
    return render(request, 'lenses/guide.html', context)


# Get Reading Powers (AJAX)
@require_GET
def get_reading_powers(request):
    """Get available reading powers for reading glasses"""
    category = LensCategory.objects.filter(
        category_type='reading',
        is_active=True
    ).first()
    
    if not category:
        return JsonResponse({'error': 'Reading category not found'}, status=404)
    
    # Get all reading lens options
    reading_options = category.lens_options.filter(is_active=True)
    
    # Collect all unique reading powers
    all_powers = set()
    for option in reading_options:
        if option.available_reading_powers:
            all_powers.update(option.available_reading_powers)
    
    # Sort powers
    sorted_powers = sorted(list(all_powers), key=lambda x: float(x.replace('+', '')))
    
    return JsonResponse({
        'success': True,
        'reading_powers': sorted_powers
    })


# Get Add-on Details (AJAX)
@require_GET
def get_addon_details(request):
    """Get detailed information about a specific add-on"""
    addon_id = request.GET.get('addon_id')
    
    if not addon_id:
        return JsonResponse({'error': 'Add-on ID required'}, status=400)
    
    try:
        addon = LensAddOn.objects.get(id=addon_id, is_active=True)
        
        data = {
            'id': addon.id,
            'name': addon.name,
            'addon_type': addon.addon_type,
            'description': addon.description,
        }
        
        return JsonResponse({
            'success': True,
            'addon': data
        })
        
    except LensAddOn.DoesNotExist:
        return JsonResponse({'error': 'Add-on not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Lens Recommendation Engine
@require_GET
def get_lens_recommendation(request):
    """Recommend lens options based on user needs"""
    # Get user preferences
    usage = request.GET.get('usage')  # 'computer', 'outdoor', 'all_day', 'reading'
    prescription_strength = request.GET.get('prescription_strength')  # 'low', 'medium', 'high'
    budget = request.GET.get('budget')  # 'economy', 'standard', 'premium'
    
    recommendations = []
    
    # Simple recommendation logic
    if usage == 'computer':
        # Recommend Prevencia or blue light options
        options = LensOption.objects.filter(
            name__icontains='prevencia',
            is_active=True
        ) | LensOption.objects.filter(
            name__icontains='blue',
            is_active=True
        )
    elif usage == 'outdoor':
        # Recommend photochromic or transition lenses
        options = LensOption.objects.filter(
            is_active=True
        )
        # Filter for options that have photochromic add-ons
    elif usage == 'reading':
        category = LensCategory.objects.filter(category_type='reading').first()
        if category:
            options = category.lens_options.filter(is_active=True)
        else:
            options = LensOption.objects.none()
    else:
        # All-day use - recommend versatile options
        options = LensOption.objects.filter(
            category__category_type='single_vision',
            is_active=True
        )
    
    # Filter by budget
    if budget == 'economy':
        options = options.filter(is_premium=False).order_by('base_price')[:3]
    elif budget == 'premium':
        options = options.filter(is_premium=True).order_by('-base_price')[:3]
    else:
        options = options.order_by('base_price')[1:4]  # Mid-range
    
    for option in options:
        recommendations.append({
            'id': option.id,
            'name': option.name,
            'description': option.description,
            'base_price': str(option.base_price),
            'lens_index': str(option.lens_index),
            'features': option.features,
            'is_premium': option.is_premium,
        })
    
    return JsonResponse({
        'success': True,
        'recommendations': recommendations
    })