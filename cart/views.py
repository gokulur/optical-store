# cart/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal

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
    """Calculate total price for a cart item including lens options and add-ons"""
    total = cart_item.unit_price * cart_item.quantity

    if cart_item.lens_price:
        total += cart_item.lens_price * cart_item.quantity

    for addon in cart_item.lens_addons.all():
        total += addon.price * cart_item.quantity

    return total


def get_cart_totals(cart):
    """Calculate all cart totals — returns total QUANTITY not distinct rows"""
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option', 'sunglass_lens_option'
    ).prefetch_related('lens_addons')

    subtotal = Decimal('0.00')
    for item in cart_items:
        subtotal += calculate_item_total(item)

    tax_rate = Decimal('0.00')
    tax = subtotal * tax_rate

    # Free shipping over QAR 200
    shipping = Decimal('0.00')
    if subtotal > 0 and subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')

    total = subtotal + tax + shipping

    # ✅ Sum all quantities — so 1 product with qty=3 counts as 3
    total_qty = cart_items.aggregate(total=Sum('quantity'))['total'] or 0

    return {
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        'item_count': total_qty,
    }


def get_product_stock(product):
    """Return effective stock limit for a product."""
    if getattr(product, 'track_inventory', False):
        stock = getattr(product, 'stock_quantity', 0)
        if stock and stock > 0:
            return stock
    return 99


def merge_guest_cart_on_login(user, session_key):
    """Merge guest cart with user cart on login"""
    try:
        guest_cart = Cart.objects.filter(session_key=session_key, customer=None).first()
        if not guest_cart:
            return

        user_cart, _ = Cart.objects.get_or_create(customer=user)

        for item in guest_cart.items.all():
            existing = user_cart.items.filter(
                product=item.product,
                variant=item.variant,
                lens_option=item.lens_option,
                sunglass_lens_option=item.sunglass_lens_option,
            ).first()

            if existing:
                existing.quantity += item.quantity
                existing.save()
                item.delete()
            else:
                item.cart = user_cart
                item.save()

        guest_cart.delete()

    except Exception as e:
        print(f"Error merging cart: {e}")


# ============================================
# CART VIEW PAGE
# ============================================

def cart_view(request):
    """Display cart contents"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        'product', 'variant', 'lens_option', 'sunglass_lens_option'
    ).prefetch_related('lens_addons', 'product__images')

    subtotal = Decimal('0.00')
    for item in cart_items:
        item.item_total = calculate_item_total(item)
        subtotal += item.item_total

    tax_rate = Decimal('0.00')
    tax = subtotal * tax_rate

    shipping = Decimal('0.00')
    if subtotal > 0 and subtotal < Decimal('200.00'):
        shipping = Decimal('20.00')

    total = subtotal + tax + shipping

    free_shipping_threshold = Decimal('200.00')
    free_shipping_remaining = max(Decimal('0.00'), free_shipping_threshold - subtotal)
    shipping_progress = (
        min(100, float(subtotal / free_shipping_threshold * 100))
        if subtotal > 0 else 0
    )

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
# UPDATE QUANTITY (AJAX)
# ============================================

def update_cart_quantity(request, item_id, action):
    """Update cart item quantity via AJAX. Accepts GET and POST."""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)

        product = cart_item.product
        stock_limit = get_product_stock(product)

        if action == 'increase':
            if cart_item.quantity >= stock_limit:
                return JsonResponse({
                    'success': False,
                    'limit_reached': True,
                    'quantity': cart_item.quantity,
                    'message': f'Only {stock_limit} unit(s) available in stock.',
                    'item_total': str(calculate_item_total(cart_item)),
                    'cart_count': get_cart_totals(cart)['item_count'],
                })

            cart_item.quantity += 1
            cart_item.save()

        elif action == 'decrease':
            if cart_item.quantity <= 1:
                return JsonResponse({
                    'success': False,
                    'block': True,
                    'quantity': cart_item.quantity,
                    'message': 'Minimum quantity is 1. Use the Remove button to delete.',
                    'item_total': str(calculate_item_total(cart_item)),
                    'cart_count': get_cart_totals(cart)['item_count'],
                })

            cart_item.quantity -= 1
            cart_item.save()

        else:
            return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)

        item_total = calculate_item_total(cart_item)
        totals = get_cart_totals(cart)

        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity,
            'item_total': str(item_total),
            'subtotal': str(totals['subtotal']),
            'shipping': str(totals['shipping']),
            'tax': str(totals['tax']),
            'cart_total': str(totals['total']),
            'cart_count': totals['item_count'],  # ✅ total quantity
            'stock_limit': stock_limit,
        })

    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Item not found in cart.'}, status=404)
    except Exception as e:
        print(f"update_cart_quantity error: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============================================
# REMOVE FROM CART (AJAX)
# ============================================

@require_http_methods(["GET", "POST"])
def remove_from_cart(request, item_id):
    """Remove item from cart via AJAX."""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)

        product_name = cart_item.product.name
        cart_item.delete()

        totals = get_cart_totals(cart)

        return JsonResponse({
            'success': True,
            'message': f'{product_name} removed from cart.',
            'cart_count': totals['item_count'],  # ✅ total quantity
            'subtotal': str(totals['subtotal']),
            'shipping': str(totals['shipping']),
            'tax': str(totals['tax']),
            'cart_total': str(totals['total']),
        })

    except Exception as e:
        print(f"remove_from_cart error: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============================================
# ADD TO CART — Simple products
# ============================================

@require_POST
def add_to_cart(request):
    """Add a simple product (accessories, etc.) to cart"""
    try:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        quantity   = max(1, int(request.POST.get('quantity', 1)))

        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

        stock = get_product_stock(product)
        if quantity > stock:
            quantity = stock

        cart = get_or_create_cart(request)

        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment

        existing = cart.items.filter(
            product=product,
            variant=variant,
            requires_prescription=False,
            lens_option__isnull=True,
            sunglass_lens_option__isnull=True,
        ).first()

        if existing:
            new_qty = min(existing.quantity + quantity, stock)
            existing.quantity = new_qty
            existing.save()
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=quantity,
                unit_price=unit_price,
                requires_prescription=False,
            )

        messages.success(request, f'{product.name} added to cart!')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart.',
                'cart_count': totals['item_count'],
                'cart_total': str(totals['total']),
            })

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error adding to cart: {e}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        return redirect('catalog:home')


# ============================================
# ADD EYEGLASS TO CART
# ============================================

@require_POST
def add_eyeglass_to_cart(request):
    """Add eyeglass with mandatory lens selection to cart"""
    try:
        product_id     = request.POST.get('product_id')
        variant_id     = request.POST.get('variant_id')
        quantity       = max(1, int(request.POST.get('quantity', 1)))
        lens_option_id = request.POST.get('lens_option_id')
        addon_ids      = request.POST.getlist('addon_ids[]')

        requires_prescription = request.POST.get('requires_prescription') == 'true'

        prescription_data = None
        if requires_prescription:
            prescription_data = {
                'right_sph':  request.POST.get('right_sph'),
                'right_cyl':  request.POST.get('right_cyl'),
                'right_axis': request.POST.get('right_axis'),
                'right_add':  request.POST.get('right_add'),
                'left_sph':   request.POST.get('left_sph'),
                'left_cyl':   request.POST.get('left_cyl'),
                'left_axis':  request.POST.get('left_axis'),
                'left_add':   request.POST.get('left_add'),
                'pd':         request.POST.get('pd'),
            }

        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)

        cart = get_or_create_cart(request)

        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment

        lens_price  = Decimal('0.00')
        lens_option = None
        if lens_option_id:
            lens_option = get_object_or_404(LensOption, id=lens_option_id)
            lens_price  = lens_option.base_price

        static_lens_price = request.POST.get('total_lens_price')
        if static_lens_price and not lens_option_id:
            try:
                lens_price = Decimal(str(static_lens_price))
            except Exception:
                pass

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
            special_instructions=request.POST.get('special_instructions', ''),
        )

        for addon_id in addon_ids:
            try:
                addon = LensAddOn.objects.get(id=addon_id)
                CartItemLensAddOn.objects.create(
                    cart_item=cart_item,
                    addon=addon,
                    price=addon.price,
                )
            except LensAddOn.DoesNotExist:
                pass

        messages.success(request, f'{product.name} with lenses added to cart!')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart.',
                'cart_count': totals['item_count'],
                'cart_total': str(totals['total']),
            })

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error adding eyeglass to cart: {e}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        return redirect('catalog:eyeglasses_list')


# ============================================
# ADD SUNGLASS TO CART
# ============================================

@require_POST
def add_sunglass_to_cart(request):
    """Add sunglass with optional lens to cart"""
    try:
        product_id            = request.POST.get('product_id')
        variant_id            = request.POST.get('variant_id')
        quantity              = max(1, int(request.POST.get('quantity', 1)))
        sunglass_lens_id      = request.POST.get('sunglass_lens_option_id')
        requires_prescription = request.POST.get('requires_prescription') == 'true'

        prescription_data = None
        if requires_prescription:
            prescription_data = {
                'right_sph':  request.POST.get('right_sph'),
                'right_cyl':  request.POST.get('right_cyl'),
                'right_axis': request.POST.get('right_axis'),
                'left_sph':   request.POST.get('left_sph'),
                'left_cyl':   request.POST.get('left_cyl'),
                'left_axis':  request.POST.get('left_axis'),
            }

        product = get_object_or_404(Product, id=product_id, is_active=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)

        cart = get_or_create_cart(request)

        unit_price = product.base_price
        if variant and variant.price_adjustment:
            unit_price += variant.price_adjustment

        lens_price           = Decimal('0.00')
        sunglass_lens_option = None
        if sunglass_lens_id:
            sunglass_lens_option = get_object_or_404(SunglassLensOption, id=sunglass_lens_id)
            lens_price = sunglass_lens_option.price

        CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price=unit_price,
            requires_prescription=requires_prescription,
            sunglass_lens_option=sunglass_lens_option,
            lens_price=lens_price,
            prescription_data=prescription_data,
        )

        messages.success(request, f'{product.name} added to cart!')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart.',
                'cart_count': totals['item_count'],
                'cart_total': str(totals['total']),
            })

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error adding sunglass to cart: {e}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        return redirect('catalog:sunglasses_list')


# ============================================
# ADD CONTACT LENS TO CART
# ============================================

@require_POST
def add_contact_lens_to_cart(request):
    """Add contact lens with power/color options to cart"""
    try:
        product_id  = request.POST.get('product_id')
        quantity    = max(1, int(request.POST.get('quantity', 1)))
        color_id    = request.POST.get('color_id')
        left_power  = request.POST.get('left_power')
        right_power = request.POST.get('right_power')

        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart    = get_or_create_cart(request)

        prescription_data = None
        try:
            contact_lens = product.contact_lens
            if contact_lens.lens_type == 'color' and color_id:
                color = get_object_or_404(
                    ContactLensColor, id=color_id, contact_lens=contact_lens
                )
                prescription_data = {
                    'color_id':   color_id,
                    'color_name': color.name,
                }
        except Exception:
            pass

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            unit_price=product.base_price,
            contact_lens_left_power=(Decimal(left_power)   if left_power  else None),
            contact_lens_right_power=(Decimal(right_power) if right_power else None),
            prescription_data=prescription_data,
        )

        messages.success(request, f'{product.name} added to cart!')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            totals = get_cart_totals(cart)
            return JsonResponse({
                'success': True,
                'message': 'Item added to cart.',
                'cart_count': totals['item_count'],
                'cart_total': str(totals['total']),
            })

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error adding contact lens to cart: {e}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        return redirect('catalog:contact_lenses_list')


# ============================================
# UPDATE CART ITEM (form POST)
# ============================================

@require_POST
def update_cart_item(request, item_id):
    """Update cart item quantity via standard form POST"""
    try:
        cart      = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        quantity  = int(request.POST.get('quantity', 1))

        if quantity <= 0:
            cart_item.delete()
            messages.success(request, 'Item removed from cart.')
        else:
            stock = get_product_stock(cart_item.product)
            cart_item.quantity = min(quantity, stock)
            cart_item.save()
            messages.success(request, 'Cart updated.')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            totals = get_cart_totals(cart)
            return JsonResponse({'success': True, 'cart_count': totals['item_count']})

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error updating cart: {e}')
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
        messages.success(request, 'Cart cleared.')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'cart_count': 0})

        return redirect('cart:cart_view')

    except Exception as e:
        messages.error(request, f'Error clearing cart: {e}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        return redirect('cart:cart_view')


# ============================================
# AJAX HELPERS
# ============================================

def get_cart_count(request):
    """Return current cart total quantity"""
    cart   = get_or_create_cart(request)
    result = cart.items.aggregate(total=Sum('quantity'))
    count  = result['total'] or 0
    return JsonResponse({'count': count})


def get_cart_summary(request):
    """Return cart summary for header mini-cart"""
    cart       = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'variant').prefetch_related('product__images')

    items_data = []
    subtotal   = Decimal('0.00')

    for item in cart_items:
        item_total = calculate_item_total(item)
        subtotal  += item_total
        first_img  = item.product.images.first()

        items_data.append({
            'id':           item.id,
            'product_name': item.product.name,
            'variant_name': item.variant.color_name if item.variant else None,
            'quantity':     item.quantity,
            'unit_price':   str(item.unit_price),
            'item_total':   str(item_total),
            'image_url':    first_img.image.url if first_img else None,
            'product_url':  f'/products/{item.product.slug}/',
        })

    total_qty = cart_items.aggregate(total=Sum('quantity'))['total'] or 0

    return JsonResponse({
        'items':    items_data,
        'subtotal': str(subtotal),
        'count':    total_qty,
    })


def buy_now(request, product_id):
    """Store buy-now product in session, redirect to checkout."""
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        request.session['buy_now'] = {
            'product_id': product_id,
            'quantity': quantity
        }
        return JsonResponse({'redirect': '/orders/checkout/?buy_now=1'})
    return redirect('orders:checkout')