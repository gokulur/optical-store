# orders/payment_services.py
"""
Payment Gateway Integration Services
Supports: Stripe, Razorpay, PayPal, Sadad (Qatar)
"""

from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import hmac
import hashlib
import requests
import uuid

# ── Stripe ────────────────────────────────────────────────────
try:
    import stripe
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
except ImportError:
    stripe = None

# ── Razorpay ──────────────────────────────────────────────────
try:
    import razorpay
    razorpay_client = razorpay.Client(
        auth=(
            getattr(settings, 'RAZORPAY_KEY_ID', ''),
            getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        )
    ) if getattr(settings, 'RAZORPAY_KEY_ID', '') else None
except ImportError:
    razorpay_client = None

# ── PayPal ────────────────────────────────────────────────────
try:
    from paypalrestsdk import Payment as PayPalPayment
    import paypalrestsdk
    paypalrestsdk.configure({
        "mode":          getattr(settings, 'PAYPAL_MODE', 'sandbox'),
        "client_id":     getattr(settings, 'PAYPAL_CLIENT_ID', ''),
        "client_secret": getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
    })
except ImportError:
    PayPalPayment = None


class PaymentGatewayError(Exception):
    """Custom exception for payment gateway errors"""
    pass


# ══════════════════════════════════════════════════════════════
# STRIPE
# ══════════════════════════════════════════════════════════════

class StripePaymentService:
    """Stripe payment integration"""

    @staticmethod
    def create_payment_intent(order):
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),
                currency=order.currency.lower(),
                description=f"Order {order.order_number}",
                metadata={
                    'order_id':      str(order.id),
                    'order_number':  order.order_number,
                    'customer_email':order.customer_email,
                },
                receipt_email=order.customer_email,
            )
            return {
                'success':           True,
                'client_secret':     intent.client_secret,
                'payment_intent_id': intent.id,
                'amount':            order.total_amount,
                'currency':          order.currency,
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def confirm_payment(payment_intent_id):
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                'success':        intent.status == 'succeeded',
                'status':         intent.status,
                'payment_intent': intent,
                'amount':         Decimal(intent.amount) / 100,
                'currency':       intent.currency.upper(),
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def create_refund(payment_intent_id, amount=None):
        if not stripe:
            raise PaymentGatewayError("Stripe is not configured")
        try:
            params = {'payment_intent': payment_intent_id}
            if amount:
                params['amount'] = int(amount * 100)
            refund = stripe.Refund.create(**params)
            return {
                'success':   True,
                'refund_id': refund.id,
                'status':    refund.status,
                'amount':    Decimal(refund.amount) / 100,
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# RAZORPAY
# ══════════════════════════════════════════════════════════════

class RazorpayPaymentService:
    """Razorpay payment integration (popular in India)"""

    @staticmethod
    def create_order(order):
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        try:
            rp_order = razorpay_client.order.create({
                'amount':   int(order.total_amount * 100),
                'currency': order.currency,
                'receipt':  order.order_number,
                'notes':    {
                    'order_id':      str(order.id),
                    'order_number':  order.order_number,
                    'customer_email':order.customer_email,
                }
            })
            return {
                'success':           True,
                'razorpay_order_id': rp_order['id'],
                'amount':            order.total_amount,
                'currency':          order.currency,
                'key_id':            settings.RAZORPAY_KEY_ID,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        try:
            params_dict = {
                'razorpay_order_id':   razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature':  razorpay_signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)
            payment = razorpay_client.payment.fetch(razorpay_payment_id)
            return {
                'success':      True,
                'payment_id':   razorpay_payment_id,
                'order_id':     razorpay_order_id,
                'status':       payment['status'],
                'amount':       Decimal(payment['amount']) / 100,
                'method':       payment.get('method', ''),
                'card_last4':   payment.get('card', {}).get('last4', ''),
                'card_network': payment.get('card', {}).get('network', ''),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def create_refund(payment_id, amount=None):
        if not razorpay_client:
            raise PaymentGatewayError("Razorpay is not configured")
        try:
            params = {'payment_id': payment_id}
            if amount:
                params['amount'] = int(amount * 100)
            refund = razorpay_client.refund.create(**params)
            return {
                'success':   True,
                'refund_id': refund['id'],
                'status':    refund['status'],
                'amount':    Decimal(refund['amount']) / 100,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# PAYPAL
# ══════════════════════════════════════════════════════════════

class PayPalPaymentService:
    """PayPal payment integration"""

    @staticmethod
    def create_payment(order, return_url, cancel_url):
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        try:
            payment = PayPalPayment({
                "intent": "sale",
                "payer":  {"payment_method": "paypal"},
                "redirect_urls": {"return_url": return_url, "cancel_url": cancel_url},
                "transactions": [{
                    "item_list": {"items": [{
                        "name":     f"Order {order.order_number}",
                        "sku":      order.order_number,
                        "price":    str(order.total_amount),
                        "currency": order.currency,
                        "quantity": 1
                    }]},
                    "amount": {"total": str(order.total_amount), "currency": order.currency},
                    "description": f"Payment for Order {order.order_number}"
                }]
            })
            if payment.create():
                for link in payment.links:
                    if link.rel == "approval_url":
                        return {
                            'success':      True,
                            'payment_id':   payment.id,
                            'approval_url': str(link.href),
                        }
            return {'success': False, 'error': payment.error}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def execute_payment(payment_id, payer_id):
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        try:
            payment = PayPalPayment.find(payment_id)
            if payment.execute({"payer_id": payer_id}):
                return {
                    'success':     True,
                    'payment_id':  payment.id,
                    'state':       payment.state,
                    'payer_email': payment.payer.get('payer_info', {}).get('email', ''),
                }
            return {'success': False, 'error': payment.error}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def create_refund(sale_id, amount=None):
        if not PayPalPayment:
            raise PaymentGatewayError("PayPal is not configured")
        try:
            from paypalrestsdk import Sale
            sale   = Sale.find(sale_id)
            params = {}
            if amount:
                params['amount'] = {'total': str(amount), 'currency': 'USD'}
            refund = sale.refund(params)
            if refund.success():
                return {'success': True, 'refund_id': refund.id, 'state': refund.state}
            return {'success': False, 'error': refund.error}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# SADAD  (Qatar)
# ══════════════════════════════════════════════════════════════

class SadadPaymentError(Exception):
    pass


class SadadPaymentService:
    """
    Sadad (Qatar) payment integration.

    Required settings (settings.py):
        SADAD_MERCHANT_ID  = "your-merchant-id"
        SADAD_API_KEY      = "your-api-key"       # Bearer token
        SADAD_SECRET_KEY   = "your-secret-key"    # HMAC signature
        SADAD_BASE_URL     = "https://api-gateway.sadad.qa"          # production
                          or "https://api-gateway-sandbox.sadad.qa"  # sandbox
        SADAD_RETURN_URL   = "https://yoursite.com/orders/payment/sadad/return/"
    """

    BASE_URL    = getattr(settings, 'SADAD_BASE_URL',    'https://api-gateway-sandbox.sadad.qa')
    MERCHANT_ID = getattr(settings, 'SADAD_MERCHANT_ID', '')
    API_KEY     = getattr(settings, 'SADAD_API_KEY',     '')
    SECRET_KEY  = getattr(settings, 'SADAD_SECRET_KEY',  '')
    RETURN_URL  = getattr(settings, 'SADAD_RETURN_URL',  '')

    @classmethod
    def _headers(cls):
        return {
            'Authorization': f'Bearer {cls.API_KEY}',
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }

    # ----------------------------------------------------------
    @classmethod
    def create_invoice(cls, order) -> dict:
        """
        Create a Sadad payment invoice.
        Endpoint: POST /payment/api/v1/Init
        """
        if not cls.MERCHANT_ID or not cls.API_KEY:
            raise SadadPaymentError(
                "Sadad credentials not configured. "
                "Set SADAD_MERCHANT_ID, SADAD_API_KEY, SADAD_SECRET_KEY, "
                "SADAD_RETURN_URL in settings.py"
            )

        payload = {
            "MerchantId":    cls.MERCHANT_ID,
            "OrderId":       order.order_number,
            "Amount":        str(order.total_amount),
            "Currency":      getattr(order, 'currency', 'QAR'),
            "Description":   f"Payment for order {order.order_number}",
            "ReturnUrl":     cls.RETURN_URL,
            "CustomerName":  getattr(order, 'customer_name',  ''),
            "CustomerEmail": getattr(order, 'customer_email', ''),
            "CustomerPhone": getattr(order, 'customer_phone', ''),
            "Lang":          "en",
        }

        try:
            resp = requests.post(
                f"{cls.BASE_URL}/payment/api/v1/Init",
                json=payload,
                headers=cls._headers(),
                timeout=30,
            )
            data = resp.json()
        except requests.RequestException as exc:
            return {'success': False, 'error': str(exc)}

        if resp.status_code == 200 and data.get('IsSuccess'):
            return {
                'success':     True,
                'invoice_id':  str(data.get('InvoiceId', '')),
                'invoice_key': data.get('InvoiceKey', ''),
                'payment_url': data.get('PaymentUrl') or data.get('InvoiceURL', ''),
                'raw':         data,
            }

        return {
            'success': False,
            'error':   data.get('Message') or data.get('error') or f"HTTP {resp.status_code}: {data}",
            'raw':     data,
        }

    # ----------------------------------------------------------
    @classmethod
    def verify_payment(cls, invoice_id: str) -> dict:
        """
        Verify a Sadad invoice server-side.
        Endpoint: POST /payment/api/v1/InquireInvoice
        """
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/payment/api/v1/InquireInvoice",
                json={"InvoiceId": invoice_id},
                headers=cls._headers(),
                timeout=30,
            )
            data = resp.json()
        except requests.RequestException as exc:
            return {'paid': False, 'error': str(exc)}

        status = data.get('InvoiceStatus')
        paid   = status in (2, '2', 'Paid', 'paid', 'PAID')

        return {
            'paid':           paid,
            'status':         str(status),
            'invoice_id':     invoice_id,
            'transaction_id': str(data.get('TransactionId', '')),
            'amount':         str(data.get('InvoiceValue', '')),
            'raw':            data,
        }


# ══════════════════════════════════════════════════════════════
# FACTORY
# ══════════════════════════════════════════════════════════════

class PaymentGatewayFactory:
    """Factory to get appropriate payment service"""

    GATEWAYS = {
        'stripe':   StripePaymentService,
        'razorpay': RazorpayPaymentService,
        'paypal':   PayPalPaymentService,
        'sadad':    SadadPaymentService,
    }

    @classmethod
    def get_service(cls, gateway_name):
        service = cls.GATEWAYS.get(gateway_name.lower())
        if not service:
            raise PaymentGatewayError(f"Unsupported payment gateway: {gateway_name}")
        return service