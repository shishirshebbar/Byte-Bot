"""In-memory QR decoding and UPI payment-intent parsing.

A UPI QR (`upi://pay?pa=...&am=...`) always starts a payment *from* the person who
scans it. Byte Bot uses that fact to show that a "refund QR" sends money out.
Image bytes never leave memory; only the parsed payee and amount are kept.
"""
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, parse_qs

VPA = re.compile(r'^[\w.+-]{2,}@[a-zA-Z][a-zA-Z0-9_-]{1,}$')


def decode(image):
    """Return the QR payload strings found in a PIL RGB image (empty when none)."""
    try:
        import cv2
        import numpy as np
    except ImportError:  # OpenCV ships with EasyOCR; without it QR checks are skipped.
        return []
    array = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    try:
        found, payloads, _, _ = detector.detectAndDecodeMulti(array)
    except cv2.error:
        found, payloads = False, ()
    values = [p for p in payloads if p] if found else []
    if not values:
        value, _, _ = detector.detectAndDecode(array)
        values = [value] if value else []
    return values[:5]


def parse_upi(payload):
    """Parse a UPI payment URI into a minimal, validated payment intent, or None."""
    if not isinstance(payload, str) or len(payload) > 1000:
        return None
    parts = urlsplit(payload.strip())
    if parts.scheme.lower() != 'upi' or parts.netloc.lower() not in ('pay', 'mandate'):
        return None
    query = {k.lower(): v[0] for k, v in parse_qs(parts.query).items() if v}
    payee = query.get('pa', '').strip()
    if not VPA.fullmatch(payee):
        return None
    amount = None
    if query.get('am'):
        try:
            value = Decimal(query['am'])
            if 0 < value < Decimal('10000000'):
                amount = int(value * 100)
        except InvalidOperation:
            pass
    name = re.sub(r'[^\w .\'-]', '', query.get('pn', ''))[:60] or None
    return {'payee_vpa': payee.casefold(), 'payee_name': name, 'amount_paise': amount,
            'mandate': parts.netloc.lower() == 'mandate', 'initiates_payment': True}


def payment_intents(image):
    intents = []
    for payload in decode(image):
        intent = parse_upi(payload)
        if intent and intent not in intents:
            intents.append(intent)
    return intents


def describe(intent):
    amount = f"₹{intent['amount_paise'] // 100:,}" if intent.get('amount_paise') else 'an amount you choose'
    return f"[QR code] UPI payment of {amount} to {intent['payee_vpa']}"
