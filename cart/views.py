# cart/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.db.models import Sum

from .models import Cart, CartItem, CartItemLensAddOn
from catalog.models import Product, ProductVariant, ContactLensColor
from lenses.models import LensOption, LensAddOn, SunglassLensOption


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_or_create_cart(request):
    """Get or create cart for user or session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            customer=request.user,
            defaults={'currency': request.session.get('currency', 'QAR')}
        )
    else:
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            customer=None,
            defaults={'currency': request.session.get('currency', 'QAR')}
        )
    
    return cart


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


def get_cart_totals(cart):
    """Calculate all cart totals"""
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option', 'sunglass_lens_option'
    ).prefetch_related('lens_addons')
    
    subtotal = Decimal('0.00')
    for item in cart_items:
        item_total = calculate_item_total(item)
        subtotal += item_total
    
    # Tax and shipping
    tax_rate = Decimal('0.00')
    tax = subtotal * tax_rate
    
    # Shipping logic
    shipping = Decimal('0.00')
    if subtotal > 0 and subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')
    
    total = subtotal + tax + shipping
    
    return {
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        'item_count': cart_items.count()
    }


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


# ============================================
# CART VIEW PAGE
# ============================================

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
    
    # Tax and shipping
    tax_rate = Decimal('0.00')
    tax = subtotal * tax_rate
    
    shipping = Decimal('0.00')
    if subtotal > 0 and subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')
    
    total = subtotal + tax + shipping
    
    # Free shipping progress
    free_shipping_threshold = Decimal('200.00')
    free_shipping_remaining = max(Decimal('0.00'), free_shipping_threshold - subtotal)
    shipping_progress = min(100, (subtotal / free_shipping_threshold * 100)) if subtotal > 0 else 0
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        'item_count': cart_items.count(),
        'free_shipping_remaining': free_shipping_remaining,
        'shipping_progress': shipping_progress,
    }
    
    return render(request, 'cart.html', context)


# ============================================
# UPDATE QUANTITY - SIMPLIFIED (AJAX)
# ============================================

def update_cart_quantity(request, item_id, action):
    """Update cart item quantity via AJAX - FIXED VERSION"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        # Get product stock (if available)
        product = cart_item.product
        stock_limit = getattr(product, 'stock', 999)  # Default high if no stock field
        
        if action == 'increase':
            # Check stock limit
            if cart_item.quantity >= stock_limit:
                return JsonResponse({
                    'success': False,
                    'limit_reached': True,
                    'quantity': cart_item.quantity,
                    'message': f'Maximum stock ({stock_limit}) reached!',
                    'item_total': str(calculate_item_total(cart_item)),
                    'cart_count': cart.items.count()
                })
            
            # Increase quantity
            cart_item.quantity += 1
            cart_item.save()
            
        elif action == 'decrease':
            # Check minimum quantity
            if cart_item.quantity <= 1:
                return JsonResponse({
                    'success': False,
                    'block': True,
                    'quantity': cart_item.quantity,
                    'message': 'Minimum quantity is 1. Use Remove button to delete item.',
                    'item_total': str(calculate_item_total(cart_item)),
                    'cart_count': cart.items.count()
                })
            
            # Decrease quantity
            cart_item.quantity -= 1
            cart_item.save()
        
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid action'
            }, status=400)
        
        # Calculate new item total
        item_total = calculate_item_total(cart_item)
        
        # Get updated cart totals
        totals = get_cart_totals(cart)
        
        # Return JSON response
        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity,
            'item_total': str(item_total),
            'subtotal': str(totals['subtotal']),
            'shipping': str(totals['shipping']),
            'tax': str(totals['tax']),
            'cart_total': str(totals['total']),
            'cart_count': totals['item_count']
        })
        
    except CartItem.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Item not found in cart'
        }, status=404)
    except Exception as e:
        print(f"Update quantity error: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


# ============================================
# REMOVE FROM CART (AJAX)
# ============================================

@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart via AJAX"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        product_name = cart_item.product.name
        cart_item.delete()
        
        # Get updated totals
        totals = get_cart_totals(cart)
        
        return JsonResponse({
            'success': True,
            'message': f'{product_name} removed from cart',
            'cart_count': totals['item_count'],
            'subtotal': str(totals['subtotal']),
            'shipping': str(totals['shipping']),
            'tax': str(totals['tax']),
            'cart_total': str(totals['total'])
        })
        
    except Exception as e:
        print(f"Remove from cart error: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


# ============================================
# ADD TO CART (Simple)
# ============================================

@require_POST
def add_to_cart(request):
    """Add item to cart"""
    try:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        
        cart = get_or_create_cart(request)
        
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        existing_item = cart.items.filter(
            product=product,
            variant=variant,
            requires_prescription=False
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            item = existing_item
        else:
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
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': totals['item_count'],
                'cart_total': str(totals['total'])
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:home')


# ============================================
# ADD EYEGLASS TO CART
# ============================================

@require_POST
def add_eyeglass_to_cart(request):
    """Add eyeglass with lens options to cart"""
    try:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        lens_option_id = request.POST.get('lens_option_id')
        addon_ids = request.POST.getlist('addon_ids[]')
        
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
                'pd': request.POST.get('pd'),
            }
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        
        cart = get_or_create_cart(request)
        
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        lens_price = Decimal('0.00')
        lens_option = None
        if lens_option_id:
            lens_option = get_object_or_404(LensOption, id=lens_option_id)
            lens_price = lens_option.base_price
        
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
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': totals['item_count']
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:eyeglasses_list')


# ============================================
# ADD SUNGLASS TO CART
# ============================================

@require_POST
def add_sunglass_to_cart(request):
    """Add sunglass with lens options to cart"""
    try:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))
        
        sunglass_lens_option_id = request.POST.get('sunglass_lens_option_id')
        requires_prescription = request.POST.get('requires_prescription') == 'true'
        
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
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        
        cart = get_or_create_cart(request)
        
        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment
        
        lens_price = Decimal('0.00')
        sunglass_lens_option = None
        if sunglass_lens_option_id:
            sunglass_lens_option = get_object_or_404(SunglassLensOption, id=sunglass_lens_option_id)
            lens_price = sunglass_lens_option.price
        
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
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': totals['item_count']
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:sunglasses_list')


# ============================================
# ADD CONTACT LENS TO CART
# ============================================

@require_POST
def add_contact_lens_to_cart(request):
    """Add contact lens with power options to cart"""
    try:
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        color_id = request.POST.get('color_id')
        
        left_power = request.POST.get('left_power')
        right_power = request.POST.get('right_power')
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart = get_or_create_cart(request)
        
        prescription_data = None
        if product.product_type == 'contact_lenses':
            contact_lens = product.contact_lens
            if contact_lens.lens_type == 'color' and color_id:
                color = get_object_or_404(ContactLensColor, id=color_id, contact_lens=contact_lens)
                prescription_data = {
                    'color_id': color_id,
                    'color_name': color.name
                }
        
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
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart',
                'cart_count': totals['item_count']
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error adding item to cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('catalog:contact_lenses_list')


# ============================================
# UPDATE CART ITEM
# ============================================

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
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Cart updated',
                'cart_count': totals['item_count']
            })
        
        return redirect('cart:cart_view')
        
    except Exception as e:
        messages.error(request, f'Error updating cart: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
        return redirect('cart:cart_view')


# ============================================
# CLEAR CART
# ============================================

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


# ============================================
# GET CART COUNT (AJAX)
# ============================================

def get_cart_count(request):
    """AJAX endpoint to get cart item count"""
    cart = get_or_create_cart(request)
    count = cart.items.count()
    
    return JsonResponse({'count': count})


# ============================================
# GET CART SUMMARY (AJAX)
# ============================================

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