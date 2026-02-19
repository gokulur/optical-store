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
import json
import random
import string
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

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
    pass


# ══════════════════════════════════════════════════════════════
# STRIPE
# ══════════════════════════════════════════════════════════════

class StripePaymentService:

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
                    'order_id':       str(order.id),
                    'order_number':   order.order_number,
                    'customer_email': order.customer_email,
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
                'success':  intent.status == 'succeeded',
                'status':   intent.status,
                'amount':   Decimal(intent.amount) / 100,
                'currency': intent.currency.upper(),
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
            return {'success': True, 'refund_id': refund.id, 'status': refund.status, 'amount': Decimal(refund.amount) / 100}
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# RAZORPAY
# ══════════════════════════════════════════════════════════════

class RazorpayPaymentService:

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
                    'order_id':       str(order.id),
                    'order_number':   order.order_number,
                    'customer_email': order.customer_email,
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
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id':   razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature':  razorpay_signature
            })
            payment = razorpay_client.payment.fetch(razorpay_payment_id)
            return {
                'success':      True,
                'payment_id':   razorpay_payment_id,
                'order_id':     razorpay_order_id,
                'status':       payment['status'],
                'amount':       Decimal(payment['amount']) / 100,
                'method':       payment.get('method', ''),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# PAYPAL
# ══════════════════════════════════════════════════════════════

class PayPalPaymentService:

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
                    "amount":      {"total": str(order.total_amount), "currency": order.currency},
                    "description": f"Payment for Order {order.order_number}"
                }]
            })
            if payment.create():
                for link in payment.links:
                    if link.rel == "approval_url":
                        return {'success': True, 'payment_id': payment.id, 'approval_url': str(link.href)}
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
                return {'success': True, 'payment_id': payment.id, 'state': payment.state}
            return {'success': False, 'error': payment.error}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ══════════════════════════════════════════════════════════════
# SADAD  (Qatar) — Web Checkout 2.1
# ══════════════════════════════════════════════════════════════
#
#  CRITICAL FIXES applied here:
#  1. ORDER_ID must be alphanumeric only — strip hyphens from order number
#  2. CALLBACK_URL must be a real public URL (set SADAD_RETURN_URL in .env
#     to your ngrok / production URL, e.g. https://abc.ngrok.io/orders/payment/sadad/return/)
#  3. productdetail field names must match Sadad's exact spec
#  4. TXN_DATE format must be YYYY-MM-DD HH:MM:SS
#
# ══════════════════════════════════════════════════════════════

class SadadPaymentError(Exception):
    pass


class SadadPaymentService:
    """
    Sadad (Qatar) Web Checkout 2.1.

    Required .env settings:
        SADAD_MERCHANT_ID  = "4485154"
        SADAD_SECRET_KEY   = "ecVpXr/XsjX+Fu67"
        SADAD_WEBSITE      = "alameenoptics.com"
        SADAD_RETURN_URL   = "https://YOUR-PUBLIC-DOMAIN.com/orders/payment/sadad/return/"
        SADAD_SANDBOX      = True   (False for production)

    LOCAL DEVELOPMENT:
        Use ngrok: ngrok http 8000
        Then set SADAD_RETURN_URL=https://xxxx.ngrok.io/orders/payment/sadad/return/
    """

    MERCHANT_ID = getattr(settings, 'SADAD_MERCHANT_ID', '')
    SECRET_KEY  = getattr(settings, 'SADAD_SECRET_KEY',  '')
    WEBSITE     = getattr(settings, 'SADAD_WEBSITE',     'alameenoptics.com')
    RETURN_URL  = getattr(settings, 'SADAD_RETURN_URL',  '')
    IS_SANDBOX  = getattr(settings, 'SADAD_SANDBOX',     True)

    @classmethod
    def _checkout_url(cls):
        return ('https://sadadqa.com/webpurchase'
                if cls.IS_SANDBOX
                else 'https://sadad.qa/webpurchase')

    @classmethod
    def _sanitize_order_id(cls, order_number: str) -> str:
        """
        Sadad ORDER_ID must be alphanumeric only (no hyphens, spaces, etc.).
        Strip all non-alphanumeric characters and limit to 20 chars.
        e.g. "ORD-20250219-ABC123"  →  "ORD20250219ABC123"
        """
        return re.sub(r'[^A-Za-z0-9]', '', order_number)[:20]

    # ── AES-128-CBC (matches Sadad PHP encrypt_e / decrypt_e) ──

    @classmethod
    def _encrypt(cls, data: str, key: str) -> str:
        iv        = b'@@@@&&&&####$$$$'
        key_bytes = key.encode('utf-8')[:16].ljust(16, b'\0')
        cipher    = AES.new(key_bytes, AES.MODE_CBC, iv)
        padded    = pad(data.encode('utf-8'), AES.block_size)
        return base64.b64encode(cipher.encrypt(padded)).decode('utf-8')

    @classmethod
    def _decrypt(cls, crypt: str, key: str) -> str:
        iv        = b'@@@@&&&&####$$$$'
        key_bytes = key.encode('utf-8')[:16].ljust(16, b'\0')
        cipher    = AES.new(key_bytes, AES.MODE_CBC, iv)
        decoded   = base64.b64decode(crypt)
        return unpad(cipher.decrypt(decoded), AES.block_size).decode('utf-8')

    @classmethod
    def _generate_salt(cls, length: int = 4) -> str:
        chars = 'AbcDE123IJKLMN67QRSTUVWXYZaBCdefghijklmn123opq45rs67tuv89wxyz0FGH45OP89'
        return ''.join(random.choices(chars, k=length))

    @classmethod
    def _generate_checksum(cls, checksum_input: dict) -> str:
        import urllib.parse
        secret_encoded  = urllib.parse.quote(cls.SECRET_KEY, safe='')
        salt            = cls._generate_salt(4)
        payload         = {'postData': checksum_input, 'secretKey': secret_encoded}
        json_str        = json.dumps(payload, separators=(',', ':'))
        final_string    = f"{json_str}|{salt}"
        hash_val        = hashlib.sha256(final_string.encode('utf-8')).hexdigest()
        encryption_key  = secret_encoded + cls.MERCHANT_ID
        return cls._encrypt(hash_val + salt, encryption_key)

    # ── Public: build form data ─────────────────────────────────

    @classmethod
    def build_payment_form_data(cls, order) -> dict:
        """
        Build POST fields for Sadad Web Checkout 2.1.

        Returns dict with:
            action_url  — the Sadad endpoint to POST to
            fields      — all form fields including checksumhash
        """
        if not cls.MERCHANT_ID or not cls.SECRET_KEY:
            raise SadadPaymentError(
                "Sadad credentials missing. "
                "Set SADAD_MERCHANT_ID and SADAD_SECRET_KEY in your .env file."
            )

        if not cls.RETURN_URL or 'localhost' in cls.RETURN_URL or '127.0.0.1' in cls.RETURN_URL:
            raise SadadPaymentError(
                "SADAD_RETURN_URL cannot be localhost/127.0.0.1 — "
                "Sadad servers cannot reach your local machine. "
                "Use ngrok (https://ngrok.com) for local testing: "
                "run 'ngrok http 8000' and set SADAD_RETURN_URL=https://xxxx.ngrok.io/orders/payment/sadad/return/"
            )

        # Alphanumeric-only order ID
        safe_order_id = cls._sanitize_order_id(order.order_number)
        txn_date      = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        amount        = f"{float(order.total_amount):.2f}"

        # Phone — digits only, fallback to merchant's number
        phone = re.sub(r'[^0-9]', '', getattr(order, 'customer_phone', '') or '')
        if not phone:
            phone = '97412345678'

        # ── Core POST fields ─────────────────────────────────────
        form_fields = {
            'merchant_id':                     cls.MERCHANT_ID,
            'ORDER_ID':                        safe_order_id,
            'WEBSITE':                         cls.WEBSITE,
            'TXN_AMOUNT':                      amount,
            'CUST_ID':                         order.customer_email,
            'EMAIL':                           order.customer_email,
            'MOBILE_NO':                       phone,
            'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': 'ENG',
            'VERSION':                         '1.1',
            'CALLBACK_URL':                    cls.RETURN_URL,
            'txnDate':                         txn_date,
        }

        # ── Product detail (nested structure for checksum) ───────
        product_detail = [{
            'order_id': safe_order_id,
            'itemname': f'Order {safe_order_id}',
            'amount':   amount,
            'quantity': '1',
            'type':     'line_item',
        }]

        # Checksum input = flat fields + productdetail array
        checksum_input = dict(form_fields)
        checksum_input['productdetail'] = product_detail

        checksumhash = cls._generate_checksum(checksum_input)

        # ── Final flat POST fields (productdetail as indexed keys) ─
        all_fields = dict(form_fields)
        all_fields['productdetail[0][order_id]']  = safe_order_id
        all_fields['productdetail[0][itemname]']  = f'Order {safe_order_id}'
        all_fields['productdetail[0][amount]']    = amount
        all_fields['productdetail[0][quantity]']  = '1'
        all_fields['productdetail[0][type]']      = 'line_item'
        all_fields['checksumhash']                = checksumhash

        return {
            'action_url':     cls._checkout_url(),
            'fields':         all_fields,
            'safe_order_id':  safe_order_id,   # store this in the order
        }

    # ── Public: verify callback ─────────────────────────────────

    @classmethod
    def verify_callback(cls, post_data: dict) -> dict:
        """
        Verify POST callback from Sadad after payment.
        RESPCODE == '1' means success.
        """
        import urllib.parse

        checksumhash = post_data.get('checksumhash', '')
        data_copy    = {k: v for k, v in post_data.items() if k != 'checksumhash'}

        checksum_valid = False
        try:
            secret_encoded  = urllib.parse.quote(cls.SECRET_KEY, safe='')
            encryption_key  = secret_encoded + cls.MERCHANT_ID
            decrypted       = cls._decrypt(checksumhash, encryption_key)
            salt            = decrypted[-4:]
            received_hash   = decrypted[:-4]

            verify_payload  = {'postData': data_copy, 'secretKey': secret_encoded}
            json_str        = json.dumps(verify_payload, separators=(',', ':'))
            final_string    = f"{json_str}|{salt}"
            computed_hash   = hashlib.sha256(final_string.encode('utf-8')).hexdigest()
            checksum_valid  = (computed_hash == received_hash)
        except Exception:
            checksum_valid = False

        resp_code = str(post_data.get('RESPCODE', ''))
        paid      = checksum_valid and resp_code == '1'

        return {
            'paid':           paid,
            'checksum_valid': checksum_valid,
            'resp_code':      resp_code,
            'resp_msg':       post_data.get('RESPMSG', ''),
            'order_id':       post_data.get('ORDERID', ''),
            'transaction_id': post_data.get('transaction_number', ''),
            'amount':         post_data.get('TXNAMOUNT', ''),
            'raw':            post_data,
        }


# ══════════════════════════════════════════════════════════════
# FACTORY
# ══════════════════════════════════════════════════════════════

class PaymentGatewayFactory:
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
            raise PaymentGatewayError(f"Unsupported gateway: {gateway_name}")
        return service