from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from decimal import Decimal
import json

from .models import Cart, CartItem, CartItemLensAddOn
from catalog.models import Product, ProductVariant, ContactLensColor
from lenses.models import LensOption, LensAddOn, SunglassLensOption


# Helper function to get or create cart
def get_or_create_cart(request):
    """Get or create cart for user or session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            customer=request.user,
            defaults={'currency': request.session.get('currency', 'QAR')}
        )
    else:
        # Get or create session key
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            customer=None,
            defaults={'currency': request.session.get('currency', 'QAR')}
        )
    
    return cart


def cart_view(request):
    """Display cart contents"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option', 'sunglass_lens_option'
    ).prefetch_related('lens_addons')
    
    # Calculate totals
    subtotal = Decimal('0.00')
    for item in cart_items:
        item_total = calculate_item_total(item)
        item.item_total = item_total
        subtotal += item_total
    
    # Tax and shipping (simplified)
    tax_rate = Decimal('0.00')  # Adjust based on your requirements
    tax = subtotal * tax_rate
    
    # Shipping (can be calculated based on location, weight, etc.)
    shipping = Decimal('0.00')  # Free shipping or calculate based on rules
    if subtotal > 0 and subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')  # Example shipping cost
    
    total = subtotal + tax + shipping
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        'item_count': cart_items.count(),
    }
    
    return render(request, 'cart.html', context)


def calculate_item_total(cart_item):
    """Calculate total price for a cart item including lens options"""
    total = cart_item.unit_price * cart_item.quantity
    
    # Add lens price
    if cart_item.lens_price:
        total += cart_item.lens_price * cart_item.quantity
    
    # Add lens add-ons
    for addon in cart_item.lens_addons.all():
        total += addon.price * cart_item.quantity
    
    return total


@require_POST
def add_to_cart(request):
    """Add item to cart"""
    try:
        # Get form data
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        # Get product
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        
        # Get or create cart
        cart = get_or_create_cart(request)
        
        # Determine unit price
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        # Check if item already exists in cart
        existing_item = cart.items.filter(
            product=product,
            variant=variant,
            requires_prescription=False  # Simple add without prescription
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            item = existing_item
        else:
            # Create new cart item
            item = CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=quantity,
                unit_price=unit_price,
                requires_prescription=False
            )
        
        messages.success(request, f'{product.name} added to cart successfully!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:home')


@require_POST
def add_eyeglass_to_cart(request):
    """Add eyeglass with lens options to cart"""
    try:
        # Get form data
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        # Lens options
        lens_option_id = request.POST.get('lens_option_id')
        addon_ids = request.POST.getlist('addon_ids[]')
        
        # Prescription data
        requires_prescription = request.POST.get('requires_prescription') == 'true'
        prescription_data = None
        
        if requires_prescription:
            prescription_data = {
                'right_eye': {
                    'sph': request.POST.get('right_sph'),
                    'cyl': request.POST.get('right_cyl'),
                    'axis': request.POST.get('right_axis'),
                    'add': request.POST.get('right_add'),
                },
                'left_eye': {
                    'sph': request.POST.get('left_sph'),
                    'cyl': request.POST.get('left_cyl'),
                    'axis': request.POST.get('left_axis'),
                    'add': request.POST.get('left_add'),
                },
                'pd': request.POST.get('pd'),  # Pupillary Distance
            }
        
        # Get product and variant
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        
        # Get cart
        cart = get_or_create_cart(request)
        
        # Calculate prices
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        lens_price = Decimal('0.00')
        lens_option = None
        if lens_option_id:
            lens_option = get_object_or_404(LensOption, id=lens_option_id)
            lens_price = lens_option.base_price
        
        # Create cart item
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price=unit_price,
            requires_prescription=requires_prescription,
            lens_option=lens_option,
            lens_price=lens_price,
            prescription_data=prescription_data,
            special_instructions=request.POST.get('special_instructions', '')
        )
        
        # Add lens add-ons
        if addon_ids:
            for addon_id in addon_ids:
                addon = get_object_or_404(LensAddOn, id=addon_id)
                CartItemLensAddOn.objects.create(
                    cart_item=cart_item,
                    addon=addon,
                    price=addon.price
                )
        
        messages.success(request, f'{product.name} with selected lenses added to cart!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:eyeglasses_list')


@require_POST
def add_sunglass_to_cart(request):
    """Add sunglass with lens options to cart"""
    try:
        # Get form data
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        # Sunglass lens options
        sunglass_lens_option_id = request.POST.get('sunglass_lens_option_id')
        requires_prescription = request.POST.get('requires_prescription') == 'true'
        
        # Prescription data (if applicable)
        prescription_data = None
        if requires_prescription:
            prescription_data = {
                'right_eye': {
                    'sph': request.POST.get('right_sph'),
                    'cyl': request.POST.get('right_cyl'),
                    'axis': request.POST.get('right_axis'),
                },
                'left_eye': {
                    'sph': request.POST.get('left_sph'),
                    'cyl': request.POST.get('left_cyl'),
                    'axis': request.POST.get('left_axis'),
                },
            }
        
        # Get product
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        
        # Get cart
        cart = get_or_create_cart(request)
        
        # Calculate prices
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        lens_price = Decimal('0.00')
        sunglass_lens_option = None
        if sunglass_lens_option_id:
            sunglass_lens_option = get_object_or_404(SunglassLensOption, id=sunglass_lens_option_id)
            lens_price = sunglass_lens_option.price
        
        # Create cart item
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price=unit_price,
            requires_prescription=requires_prescription,
            sunglass_lens_option=sunglass_lens_option,
            lens_price=lens_price,
            prescription_data=prescription_data
        )
        
        messages.success(request, f'{product.name} added to cart!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:sunglasses_list')


@require_POST
def add_contact_lens_to_cart(request):
    """Add contact lens with power options to cart"""
    try:
        # Get form data
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        color_id = request.POST.get('color_id')  # For color lenses
        
        # Power options
        left_power = request.POST.get('left_power')
        right_power = request.POST.get('right_power')
        
        # Get product
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Get cart
        cart = get_or_create_cart(request)
        
        # Validate color selection for color lenses
        if product.product_type == 'contact_lenses':
            contact_lens = product.contact_lens
            if contact_lens.lens_type == 'color' and color_id:
                color = get_object_or_404(ContactLensColor, id=color_id, contact_lens=contact_lens)
                # Store color info in prescription_data
                prescription_data = {
                    'color_id': color_id,
                    'color_name': color.name
                }
        else:
            prescription_data = None
        
        # Create cart item
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            unit_price=product.base_price,
            contact_lens_left_power=Decimal(left_power) if left_power else None,
            contact_lens_right_power=Decimal(right_power) if right_power else None,
            prescription_data=prescription_data
        )
        
        messages.success(request, f'{product.name} added to cart!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:contact_lenses_list')


@require_POST
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity <= 0:
            cart_item.delete()
            messages.success(request, 'Item removed from cart')
        else:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Cart updated successfully')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Cart updated',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error updating cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('cart:cart_view')


@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        product_name = cart_item.product.name
        cart_item.delete()
        
        messages.success(request, f'{product_name} removed from cart')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Item removed',
                'cart_count': cart.items.count()
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error removing item: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('cart:cart_view')


@require_POST
def clear_cart(request):
    """Clear all items from cart"""
    try:
        cart = get_or_create_cart(request)
        cart.items.all().delete()
        
        messages.success(request, 'Cart cleared successfully')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Cart cleared',
                'cart_count': 0
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error clearing cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('cart:cart_view')


def get_cart_count(request):
    """AJAX endpoint to get cart item count"""
    cart = get_or_create_cart(request)
    count = cart.items.count()
    
    return JsonResponse({'count': count})


def get_cart_summary(request):
    """AJAX endpoint to get cart summary"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'variant')
    
    items_data = []
    subtotal = Decimal('0.00')
    
    for item in cart_items:
        item_total = calculate_item_total(item)
        subtotal += item_total
        
        items_data.append({
            'id': item.id,
            'product_name': item.product.name,
            'variant_name': item.variant.color_name if item.variant else None,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'item_total': str(item_total),
            'image_url': item.product.images.first().image.url if item.product.images.first() else None
        })
    
    return JsonResponse({
        'items': items_data,
        'subtotal': str(subtotal),
        'count': cart_items.count()
    })


def merge_guest_cart_on_login(user, session_key):
    """Merge guest cart with user cart on login"""
    try:
        # Get guest cart
        guest_cart = Cart.objects.filter(session_key=session_key, customer=None).first()
        
        if not guest_cart:
            return
        
        # Get or create user cart
        user_cart, created = Cart.objects.get_or_create(customer=user)
        
        # Move items from guest cart to user cart
        for item in guest_cart.items.all():
            # Check if similar item exists in user cart
            existing_item = user_cart.items.filter(
                product=item.product,
                variant=item.variant,
                lens_option=item.lens_option,
                sunglass_lens_option=item.sunglass_lens_option
            ).first()
            
            if existing_item:
                existing_item.quantity += item.quantity
                existing_item.save()
                item.delete()
            else:
                item.cart = user_cart
                item.save()
        
        # Delete guest cart
        guest_cart.delete()
        
    except Exception as e:
        print(f"Error merging cart: {str(e)}")


