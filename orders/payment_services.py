# orders/payment_services.py
"""
Payment Gateway Integration Services
Supports: Stripe, Razorpay, PayPal
"""

from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import uuid

# Import payment libraries
try:
    import stripe
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
except ImportError:
    stripe = None

try:
    import razorpay
    razorpay_client = razorpay.Client(
        auth=(
            getattr(settings, 'RAZORPAY_KEY_ID', ''),
            getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        )
    ) if hasattr(settings, 'RAZORPAY_KEY_ID') else None
except ImportError:
    razorpay_client = None

try:
    from paypalrestsdk import Payment as PayPalPayment
    import paypalrestsdk
    paypalrestsdk.configure({
        "mode": getattr(settings, 'PAYPAL_MODE', 'sandbox'),
        "client_id": getattr(settings, 'PAYPAL_CLIENT_ID', ''),
        "client_secret": getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
    })
except ImportError:
    PayPalPayment = None


class PaymentGatewayError(Exception):
    """Custom exception for payment gateway errors"""
    pass


class StripePaymentService:
    """Stripe payment integration"""
    
    @staticmethod
    def create_payment_intent(order):
        """Create a Stripe payment intent"""
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),  # Convert to cents
                currency=order.currency.lower(),
                description=f"Order {order.order_number}",
                metadata={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'customer_email': order.customer_email,
                },
                receipt_email=order.customer_email,
            )
            
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': order.total_amount,
                'currency': order.currency,
            }
        
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def confirm_payment(payment_intent_id):
        """Confirm a Stripe payment"""
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'success': intent.status == 'succeeded',
                'status': intent.status,
                'payment_intent': intent,
                'amount': Decimal(intent.amount) / 100,
                'currency': intent.currency.upper(),
            }
        
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def create_refund(payment_intent_id, amount=None):
        """Create a refund"""
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        
        try:
            refund_params = {'payment_intent': payment_intent_id}
            if amount:
                refund_params['amount'] = int(amount * 100)
            
            refund = stripe.Refund.create(**refund_params)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': Decimal(refund.amount) / 100,
            }
        
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
            }


class RazorpayPaymentService:
    """Razorpay payment integration (popular in India)"""
    
    @staticmethod
    def create_order(order):
        """Create a Razorpay order"""
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        
        try:
            razorpay_order = razorpay_client.order.create({
                'amount': int(order.total_amount * 100),  # Convert to paise
                'currency': order.currency,
                'receipt': order.order_number,
                'notes': {
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'customer_email': order.customer_email,
                }
            })
            
            return {
                'success': True,
                'razorpay_order_id': razorpay_order['id'],
                'amount': order.total_amount,
                'currency': order.currency,
                'key_id': settings.RAZORPAY_KEY_ID,
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """Verify Razorpay payment signature"""
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        
        try:
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            razorpay_client.utility.verify_payment_signature(params_dict)
            
            # Fetch payment details
            payment = razorpay_client.payment.fetch(razorpay_payment_id)
            
            return {
                'success': True,
                'payment_id': razorpay_payment_id,
                'order_id': razorpay_order_id,
                'status': payment['status'],
                'amount': Decimal(payment['amount']) / 100,
                'method': payment.get('method', ''),
                'card_last4': payment.get('card', {}).get('last4', ''),
                'card_network': payment.get('card', {}).get('network', ''),
            }
        
        except razorpay.errors.SignatureVerificationError:
            return {
                'success': False,
                'error': 'Invalid payment signature',
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def create_refund(payment_id, amount=None):
        """Create a refund"""
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        
        try:
            refund_params = {'payment_id': payment_id}
            if amount:
                refund_params['amount'] = int(amount * 100)
            
            refund = razorpay_client.refund.create(**refund_params)
            
            return {
                'success': True,
                'refund_id': refund['id'],
                'status': refund['status'],
                'amount': Decimal(refund['amount']) / 100,
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }


class PayPalPaymentService:
    """PayPal payment integration"""
    
    @staticmethod
    def create_payment(order, return_url, cancel_url):
        """Create a PayPal payment"""
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        
        try:
            payment = PayPalPayment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": f"Order {order.order_number}",
                            "sku": order.order_number,
                            "price": str(order.total_amount),
                            "currency": order.currency,
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(order.total_amount),
                        "currency": order.currency
                    },
                    "description": f"Payment for Order {order.order_number}"
                }]
            })
            
            if payment.create():
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = str(link.href)
                        return {
                            'success': True,
                            'payment_id': payment.id,
                            'approval_url': approval_url,
                        }
            else:
                return {
                    'success': False,
                    'error': payment.error,
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def execute_payment(payment_id, payer_id):
        """Execute PayPal payment after approval"""
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        
        try:
            payment = PayPalPayment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'state': payment.state,
                    'payer_email': payment.payer.get('payer_info', {}).get('email', ''),
                }
            else:
                return {
                    'success': False,
                    'error': payment.error,
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def create_refund(sale_id, amount=None):
        """Create a PayPal refund"""
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        
        try:
            from paypalrestsdk import Sale
            sale = Sale.find(sale_id)
            
            refund_params = {}
            if amount:
                refund_params['amount'] = {
                    'total': str(amount),
                    'currency': 'USD'  # Adjust based on your needs
                }
            
            refund = sale.refund(refund_params)
            
            if refund.success():
                return {
                    'success': True,
                    'refund_id': refund.id,
                    'state': refund.state,
                }
            else:
                return {
                    'success': False,
                    'error': refund.error,
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }


# Payment Gateway Factory
class PaymentGatewayFactory:
    """Factory to get appropriate payment service"""
    
    GATEWAYS = {
        'stripe': StripePaymentService,
        'razorpay': RazorpayPaymentService,
        'paypal': PayPalPaymentService,
    }
    
    @classmethod
    def get_service(cls, gateway_name):
        """Get payment service by gateway name"""
        service = cls.GATEWAYS.get(gateway_name.lower())
        if not service:
            raise PaymentGatewayError(f"Unsupported payment gateway: {gateway_name}")
        return service