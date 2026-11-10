from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, Protocol

import razorpay

from app.config import get_settings
from app.core.errors import PaymentError


class PaymentProvider(Protocol):
    name: str
    key_id: str | None

    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> dict[str, Any]: ...
    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...
    def fetch_payment(self, payment_id: str) -> dict[str, Any]: ...
    def refund(self, payment_id: str, amount_paise: int, idempotency_key: str) -> dict[str, Any]: ...
    def order_payments(self, order_id: str) -> list[dict]: ...
    def fetch_refund(self, refund_id: str) -> dict: ...
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...


class RazorpayProvider:
    name = "razorpay"

    def __init__(self) -> None:
        settings = get_settings()
        if settings.payments_live_enabled and settings.app_env != "production":
            raise PaymentError("Live payments are locked until production cutover")
        if settings.razorpay_key_id.startswith("rzp_live_") and not settings.payments_live_enabled:
            raise PaymentError("Live Razorpay keys require PAYMENTS_LIVE_ENABLED=true")
        self.key_id = settings.razorpay_key_id
        self._secret = settings.razorpay_key_secret
        self._webhook_secret = settings.razorpay_webhook_secret
        self._client = razorpay.Client(auth=(self.key_id, self._secret))

    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
        return self._client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt[:40],
                "payment_capture": 1,
                "notes": notes,
            }
        )

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        try:
            self._client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except Exception:
            return False

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self._client.payment.fetch(payment_id)

    def refund(self, payment_id: str, amount_paise: int, idempotency_key: str) -> dict[str, Any]:
        return self._client.payment.refund(payment_id, {"amount": amount_paise},
                                           headers={"X-Refund-Idempotency": idempotency_key})

    def order_payments(self, order_id: str) -> list[dict]:
        return self._client.order.payments(order_id).get("items", [])

    def fetch_refund(self, refund_id: str) -> dict:
        return self._client.refund.fetch(refund_id)

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        try:
            self._client.utility.verify_webhook_signature(
                raw_body.decode("utf-8"),
                signature,
                self._webhook_secret,
            )
            return True
        except Exception:
            return False


class FakePaymentProvider:
    """Labeled test double used by automated tests and local demo without Razorpay keys."""

    name = "fake"

    def __init__(self) -> None:
        self.key_id = "fake_local_key"

    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
        return {
            "id": f"order_fake_{uuid.uuid4().hex[:16]}",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "notes": notes,
        }

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac.new(
            b"fake-secret",
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature) or signature == "test_signature"

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        if payment_id.startswith("pay_fail"):
            return {"id": payment_id, "status": "failed", "amount": 0, "method": "test"}
        if payment_id.startswith("pay_pending"):
            return {"id": payment_id, "status": "authorized", "amount": 0, "method": "test"}
        return {"id": payment_id, "status": "captured", "amount": 0, "method": "test"}

    def refund(self, payment_id: str, amount_paise: int, idempotency_key: str) -> dict[str, Any]:
        if payment_id.startswith("pay_refundfail"):
            raise PaymentError("Gateway refund failed")
        return {
            "id": f"rfnd_fake_{idempotency_key}",
            "payment_id": payment_id,
            "amount": amount_paise,
            "status": "processed",
        }

    def order_payments(self, order_id: str) -> list[dict]:
        return []

    def fetch_refund(self, refund_id: str) -> dict:
        return {"id": refund_id, "status": "processed"}

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(b"fake-webhook", raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature) or signature == "test_webhook"


def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.payment_provider == "razorpay":
        return RazorpayProvider()
    if settings.app_env == "production":
        raise PaymentError("The fake payment provider is disabled in production")
    return FakePaymentProvider()


def fake_signature(order_id: str, payment_id: str) -> str:
    return hmac.new(b"fake-secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def fake_webhook_signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(b"fake-webhook", raw, hashlib.sha256).hexdigest()
