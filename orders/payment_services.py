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
# SADAD  (Qatar) — Correct Web Checkout 2.1 Implementation
# ══════════════════════════════════════════════════════════════
#
# Sadad does NOT use a REST API with Bearer tokens.
# It uses a form POST to https://sadadqa.com/webpurchase
# with an AES-128-CBC encrypted checksumhash.
#
# Docs: https://developer.sadad.qa/
# ══════════════════════════════════════════════════════════════

class SadadPaymentError(Exception):
    pass


class SadadPaymentService:
    """
    Sadad (Qatar) Web Checkout 2.1 integration.

    Required settings (settings.py / .env):
        SADAD_MERCHANT_ID  = "4485154"          # Your Merchant ID (SadadId)
        SADAD_SECRET_KEY   = "ecVpXr/XsjX+Fu67" # Your Secret Key from panel
        SADAD_WEBSITE      = "alameenoptics.com" # Domain registered with Sadad
        SADAD_RETURN_URL   = "https://yoursite.com/orders/payment/sadad/return/"

    For sandbox testing, use: SADAD_SANDBOX = True (default True)
    For production, set:      SADAD_SANDBOX = False
    """

    MERCHANT_ID  = getattr(settings, 'SADAD_MERCHANT_ID',  '')
    SECRET_KEY   = getattr(settings, 'SADAD_SECRET_KEY',   '')
    WEBSITE      = getattr(settings, 'SADAD_WEBSITE',      'alameenoptics.com')
    RETURN_URL   = getattr(settings, 'SADAD_RETURN_URL',   '')
    IS_SANDBOX   = getattr(settings, 'SADAD_SANDBOX',      True)

    # Sandbox uses sadadqa.com, production uses sadad.qa
    @classmethod
    def _checkout_url(cls):
        return 'https://sadadqa.com/webpurchase' if cls.IS_SANDBOX else 'https://sadad.qa/webpurchase'

    # ── AES-128-CBC Encryption (mirrors Sadad's PHP encrypt_e) ──────────

    @classmethod
    def _encrypt(cls, data: str, key: str) -> str:
        """AES-128-CBC encrypt, same as Sadad's PHP encrypt_e()"""
        iv = b'@@@@&&&&####$$$$'
        # Decode HTML entities in key (mirrors html_entity_decode)
        key_bytes = key.encode('utf-8')[:16]  # AES-128 = 16 bytes
        # Pad key to 16 bytes if shorter
        key_bytes = key_bytes.ljust(16, b'\0')[:16]
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        padded = pad(data.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode('utf-8')

    @classmethod
    def _decrypt(cls, crypt: str, key: str) -> str:
        """AES-128-CBC decrypt, same as Sadad's PHP decrypt_e()"""
        iv = b'@@@@&&&&####$$$$'
        key_bytes = key.encode('utf-8')[:16]
        key_bytes = key_bytes.ljust(16, b'\0')[:16]
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        decoded = base64.b64decode(crypt)
        decrypted = unpad(cipher.decrypt(decoded), AES.block_size)
        return decrypted.decode('utf-8')

    @classmethod
    def _generate_salt(cls, length=4) -> str:
        """Generate random salt (mirrors Sadad's PHP generateSalt_e)"""
        chars = 'AbcDE123IJKLMN67QRSTUVWXYZaBCdefghijklmn123opq45rs67tuv89wxyz0FGH45OP89'
        return ''.join(random.choices(chars, k=length))

    @classmethod
    def _generate_checksum(cls, data: dict, order) -> str:
        """
        Generate checksumhash matching Sadad's PHP getChecksumFromString().

        Steps:
          1. Build checksum_data = {'postData': form_fields, 'secretKey': url_encoded_secret}
          2. JSON-encode it
          3. Append |salt
          4. SHA-256 hash → append salt
          5. AES-128-CBC encrypt with key = (url_encoded_secret + merchantID)
        """
        import urllib.parse
        secret_encoded = urllib.parse.quote(cls.SECRET_KEY, safe='')
        salt = cls._generate_salt(4)

        checksum_data = {
            'postData':  data,
            'secretKey': secret_encoded,
        }
        json_str = json.dumps(checksum_data, separators=(',', ':'))
        final_string = f"{json_str}|{salt}"
        hash_val = hashlib.sha256(final_string.encode('utf-8')).hexdigest()
        hash_string = hash_val + salt
        encryption_key = secret_encoded + cls.MERCHANT_ID
        return cls._encrypt(hash_string, encryption_key)

    # ── Public Methods ───────────────────────────────────────────────────

    @classmethod
    def build_payment_form_data(cls, order) -> dict:
        """
        Build the POST fields needed for the Sadad Web Checkout 2.1 form.
        Returns a dict with all fields + the checksumhash, plus the action URL.

        Usage in view:
            form_data = SadadPaymentService.build_payment_form_data(order)
            # Render a template that auto-submits a hidden form to form_data['action_url']
        """
        if not cls.MERCHANT_ID or not cls.SECRET_KEY:
            raise SadadPaymentError(
                "Sadad credentials not configured. "
                "Set SADAD_MERCHANT_ID, SADAD_SECRET_KEY, SADAD_WEBSITE, "
                "SADAD_RETURN_URL in your .env / settings.py"
            )

        from django.utils import timezone
        txn_date = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        amount   = f"{float(order.total_amount):.2f}"
        phone    = (getattr(order, 'customer_phone', '') or '').replace('+', '').replace(' ', '')
        if not phone:
            phone = '97400000000'

        # Core POST fields (order matters for checksum — must match exactly)
        form_fields = {
            'merchant_id':                    cls.MERCHANT_ID,
            'ORDER_ID':                       order.order_number,
            'WEBSITE':                        cls.WEBSITE,
            'TXN_AMOUNT':                     amount,
            'CUST_ID':                        getattr(order, 'customer_email', ''),
            'EMAIL':                          getattr(order, 'customer_email', ''),
            'MOBILE_NO':                      phone,
            'SADAD_WEBCHECKOUT_PAGE_LANGUAGE': 'ENG',
            'VERSION':                        '1.1',
            'CALLBACK_URL':                   cls.RETURN_URL,
            'txnDate':                        txn_date,
        }

        # Product detail (at least one product required)
        product_fields = {
            'productdetail[0][order_id]':  order.order_number,
            'productdetail[0][itemname]':  f'Order {order.order_number}',
            'productdetail[0][amount]':    amount,
            'productdetail[0][quantity]':  '1',
            'productdetail[0][type]':      'line_item',
        }

        # Build the checksum input (only the flat form_fields, not productdetail)
        # Add productdetail to checksum array as nested dict (mirrors PHP)
        checksum_input = dict(form_fields)
        checksum_input['productdetail'] = [{
            'order_id':  order.order_number,
            'itemname':  f'Order {order.order_number}',
            'amount':    amount,
            'quantity':  '1',
            'type':      'line_item',
        }]

        checksumhash = cls._generate_checksum(checksum_input, order)

        all_fields = {}
        all_fields.update(form_fields)
        all_fields.update(product_fields)
        all_fields['checksumhash'] = checksumhash

        return {
            'action_url': cls._checkout_url(),
            'fields':     all_fields,
        }

    @classmethod
    def verify_callback(cls, post_data: dict) -> dict:
        """
        Verify the POST callback from Sadad after payment.

        Sadad sends back:
            ORDERID, RESPCODE, RESPMSG, TXNAMOUNT, transaction_number, checksumhash

        RESPCODE == '1' means success.
        Always verify the checksumhash before trusting the result.
        """
        import urllib.parse

        checksumhash = post_data.get('checksumhash', '')
        data_copy    = {k: v for k, v in post_data.items() if k != 'checksumhash'}

        # Verify checksum
        try:
            secret_encoded   = urllib.parse.quote(cls.SECRET_KEY, safe='')
            encryption_key   = secret_encoded + cls.MERCHANT_ID
            decrypted        = cls._decrypt(checksumhash, encryption_key)
            # decrypted = sha256hash + 4-char salt
            salt             = decrypted[-4:]
            received_hash    = decrypted[:-4]

            verify_data = {
                'postData':  data_copy,
                'secretKey': secret_encoded,
            }
            json_str      = json.dumps(verify_data, separators=(',', ':'))
            final_string  = f"{json_str}|{salt}"
            computed_hash = hashlib.sha256(final_string.encode('utf-8')).hexdigest()

            checksum_valid = (computed_hash == received_hash)
        except Exception as e:
            checksum_valid = False

        resp_code = str(post_data.get('RESPCODE', ''))
        paid      = checksum_valid and resp_code == '1'

        return {
            'paid':             paid,
            'checksum_valid':   checksum_valid,
            'resp_code':        resp_code,
            'resp_msg':         post_data.get('RESPMSG', ''),
            'order_id':         post_data.get('ORDERID', ''),
            'transaction_id':   post_data.get('transaction_number', ''),
            'amount':           post_data.get('TXNAMOUNT', ''),
            'raw':              post_data,
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