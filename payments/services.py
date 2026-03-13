# payments/services.py
"""
M-Pesa STK Push integration for hub education-path payments.
Uses existing MPESA_* settings from settings.py.
"""
import base64
import requests
from datetime import datetime
from django.conf import settings
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_access_token():
    base = 'sandbox' if getattr(settings, 'MPESA_ENV', 'sandbox') == 'sandbox' else 'api'
    url  = f'https://{base}.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    r    = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=30,
    )
    try:
        return r.json()['access_token']
    except Exception as e:
        logger.error(f"M-Pesa Token Error: {e}. Status: {r.status_code}. Content: {r.text[:500]}")
        raise Exception(f"Failed to get M-Pesa access token: {r.status_code}")


def generate_password():
    ts  = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + ts
    return base64.b64encode(raw.encode()).decode(), ts


def initiate_stk_push(phone, amount, ref, description):
    """
    phone:       format 2547XXXXXXXX
    amount:      integer KES
    ref:         account reference (e.g. "MODULE-23" or "LEVEL-5")
    description: short description for the transaction
    Returns the raw Safaricom API response dict.
    """
    token   = get_access_token()
    pwd, ts = generate_password()
    base    = 'sandbox' if getattr(settings, 'MPESA_ENV', 'sandbox') == 'sandbox' else 'api'
    url     = f'https://{base}.safaricom.co.ke/mpesa/stkpush/v1/processrequest'

    payload = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password':          pwd,
        'Timestamp':         ts,
        'TransactionType':   'CustomerPayBillOnline',
        'Amount':            int(amount),
        'PartyA':            phone,
        'PartyB':            settings.MPESA_SHORTCODE,
        'PhoneNumber':       phone,
        'CallBackURL':       getattr(settings, 'MPESA_CALLBACK_URL', ''),
        'AccountReference':  ref,
        'TransactionDesc':   description,
    }
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r       = requests.post(url, json=payload, headers=headers, timeout=30)
    
    try:
        return r.json()
    except Exception as e:
        logger.error(f"M-Pesa STK JSON Error: {e}. Status: {r.status_code}. Content: {r.text[:500]}")
        return {"error": f"Gateway Error {r.status_code}", "raw": r.text[:100]}


def handle_callback(data):
    """Process Safaricom M-Pesa STK callback and update Payment + grant access."""
    from payments.models import MpesaTransaction, Payment
    from progress.models import UserModuleAccess

    stk         = data.get('Body', {}).get('stkCallback', {})
    checkout_id = stk.get('CheckoutRequestID')
    result_code = str(stk.get('ResultCode', ''))
    result_desc = stk.get('ResultDesc', '')

    try:
        txn = MpesaTransaction.objects.get(checkout_request_id=checkout_id)
    except MpesaTransaction.DoesNotExist:
        return

    txn.result_code        = result_code
    txn.result_description = result_desc
    txn.raw_callback       = data

    if result_code == '0':
        items = stk.get('CallbackMetadata', {}).get('Item', [])
        for item in items:
            if item['Name'] == 'MpesaReceiptNumber':
                txn.mpesa_receipt_number = item['Value']

        txn.payment.status       = 'completed'
        txn.payment.completed_at = timezone.now()
        txn.payment.save()
        txn.save()
        _grant_access(txn.payment)
    else:
        txn.payment.status = 'failed'
        txn.payment.save()
        txn.save()


def _grant_access(payment):
    """Create UserModuleAccess records after a successful payment."""
    from progress.models import UserModuleAccess

    if payment.payment_for == 'single_module' and payment.module:
        UserModuleAccess.objects.get_or_create(
            user=payment.user, module=payment.module,
            defaults={'access_type': 'single', 'payment': payment}
        )
    elif payment.payment_for == 'full_level' and payment.level:
        for module in payment.level.modules.filter(order__gt=2):
            UserModuleAccess.objects.get_or_create(
                user=payment.user, module=module,
                defaults={'access_type': 'full_level', 'payment': payment}
            )
