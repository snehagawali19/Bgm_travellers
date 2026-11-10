"""Rules and integration contracts that can run without a database server."""
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api.deps import get_current_admin
from app.core.errors import PaymentError
from app.core.security import create_admin_session_token, utcnow
from app.models import BookingStatus, PaymentTransactionStatus, TripStatus
from app.schemas import ScheduleIn, SeatLayoutIn
from app.services.cancellations import estimate_refund
from app.services.trips import trips_overlap


@pytest.mark.parametrize("hours,expected,eligible", [(30, 10000, True), (10, 5000, True), (2, 0, True), (0.5, 0, False), (-1, 0, False)])
def test_cancellation_windows_allow_zero_refund_before_cutoff(hours, expected, eligible):
    booking = NS(total_amount_paise=10000, booking_status=BookingStatus.CONFIRMED,
        policy_snapshot={"version": "quoted", "disclaimer": "terms", "rules": {"cutoff_minutes": 60,
            "rules": [{"min_hours_before_departure": 24, "refund_percent": 100},
                      {"min_hours_before_departure": 6, "refund_percent": 50},
                      {"min_hours_before_departure": 0, "refund_percent": 0}]}},
        trip=NS(departure_datetime=utcnow() + timedelta(hours=hours), cancellation_policy=None))
    estimate = estimate_refund(booking)
    assert estimate["estimated_refund_paise"] == expected
    assert estimate["eligible"] == eligible
    assert estimate["policy_version"] == "quoted"


def test_overnight_turnaround_boundary():
    start = utcnow().replace(hour=21)
    end = start + timedelta(hours=9)
    assert trips_overlap(start, end, end + timedelta(minutes=179), end + timedelta(hours=12), 180)
    assert not trips_overlap(start, end, end + timedelta(minutes=180), end + timedelta(hours=12), 180)


@pytest.mark.parametrize("method,path,allowed", [
    ("POST", "/counter-bookings", True), ("GET", "/bookings", True),
    ("POST", "/booking-seats/abc/check-in", True), ("GET", "/trips/abc/inventory", True),
    ("POST", "/trips", False), ("POST", "/trips/abc/cancel", False),
    ("GET", "/reports", False), ("GET", "/audit", False), ("POST", "/staff", False),
    ("PATCH", "/buses/abc", False), ("POST", "/refunds/abc/retry", False),
])
def test_booking_staff_permissions(method, path, allowed):
    admin = NS(id=uuid4(), role="booking_staff", active=True)
    db = MagicMock()
    db.get.return_value = admin
    cookie = f"bgm_admin_session={create_admin_session_token(admin.id)}; bgm_csrf=test"
    request = Request({"type": "http", "method": method, "path": "/api/v1/admin" + path,
        "headers": [(b"cookie", cookie.encode()), (b"x-csrf-token", b"test")]})
    if allowed:
        assert get_current_admin(request, db) is admin
    else:
        with pytest.raises(HTTPException) as error:
            get_current_admin(request, db)
        assert error.value.status_code == 403


@pytest.mark.parametrize("patch", [{"order_id": "wrong"}, {"amount": 99}, {"currency": "USD"}, {"currency": None}])
def test_gateway_capture_rejects_wrong_order_amount_or_currency(monkeypatch, patch):
    from app.services import booking as service
    db = MagicMock()
    order = NS(id=uuid4(), gateway_order_id="order_1", amount_paise=10000)
    booking = NS(trip_id=uuid4(), payment_orders=[order])
    monkeypatch.setattr(service, "lock_trip", lambda *_: NS(status=TripStatus.PUBLISHED))
    monkeypatch.setattr(service, "expire_holds", lambda *_: None)
    monkeypatch.setattr(service, "get_payment_provider", lambda: NS(name="razorpay"))
    monkeypatch.setattr(service, "_record_transaction", lambda *_: pytest.fail("Invalid payment must not be persisted"))
    with pytest.raises(PaymentError):
        service.confirm_paid_booking(db, booking, {"id": "pay_1", "order_id": "order_1", "amount": 10000, "currency": "INR", "status": "captured", **patch})


def test_authorized_payment_can_transition_to_captured():
    from app.services.booking import _record_transaction
    db = MagicMock()
    order = NS(id=uuid4())
    txn = NS(payment_order_id=order.id, status=PaymentTransactionStatus.AUTHORIZED)
    db.execute.return_value.scalar_one_or_none.return_value = txn
    assert _record_transaction(db, order, {"id": "pay_1", "status": "captured"}).status == PaymentTransactionStatus.CAPTURED
    _record_transaction(db, order, {"id": "pay_1", "status": "failed"})
    assert txn.status == PaymentTransactionStatus.CAPTURED


def test_refund_retry_uses_stable_idempotency_header(monkeypatch):
    from app.services import payments
    mock_client = MagicMock()
    monkeypatch.setattr(payments.razorpay, "Client", lambda **_: mock_client)
    provider = payments.RazorpayProvider()
    provider.refund("pay_1", 10000, "stable-refund-uuid")
    mock_client.payment.refund.assert_called_once_with("pay_1", {"amount": 10000}, headers={"X-Refund-Idempotency": "stable-refund-uuid"})


def test_whatsapp_request_contains_template_and_callback(monkeypatch):
    from app.services import notifications
    settings = NS(whatsapp_access_token="test-token", whatsapp_phone_number_id="123", whatsapp_api_version="v23.0",
                  whatsapp_template_name="booking_update", whatsapp_template_language="en")
    monkeypatch.setattr(notifications, "get_settings", lambda: settings)
    post = MagicMock(return_value=NS(status_code=200, json=lambda: {"messages": [{"id": "wamid_1"}]}))
    monkeypatch.setattr(notifications.httpx, "post", post)
    item = NS(id=uuid4(), message="Booking confirmed", recipient="919876543210")
    assert notifications.send_whatsapp(item) == "wamid_1"
    sent = post.call_args.kwargs["json"]
    assert sent["template"]["components"][0]["parameters"][0]["text"] == item.message
    assert sent["biz_opaque_callback_data"] == str(item.id)


def test_notification_failure_has_bounded_backoff(monkeypatch):
    from app.services import notifications
    db = MagicMock()
    item = NS(attempts=0, status="pending", next_attempt_at=utcnow())
    db.execute.return_value.scalar_one_or_none.return_value = item
    monkeypatch.setattr(notifications, "send_whatsapp", MagicMock(side_effect=RuntimeError("not configured")))
    for _ in range(5):
        assert notifications.deliver_one(db)
    assert item.status == "failed"
    assert item.attempts == 5
    assert item.next_attempt_at > utcnow()


def test_delivery_webhooks_do_not_regress_read_status():
    from app.services.notifications import record_delivery
    db = MagicMock()
    item = NS(status="read", attempts=1)
    db.execute.return_value.scalar_one_or_none.return_value = item
    for status in ("sent", "delivered", "failed"):
        record_delivery(db, {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid_1", "status": status}]}}]}]})
        assert item.status == "read"


@pytest.mark.parametrize("days", [[0, 0], [7], [-1]])
def test_schedule_rejects_invalid_weekdays(days):
    with pytest.raises(ValidationError):
        ScheduleIn(name="test", route_id=uuid4(), bus_id=uuid4(), departure_time="21:30", duration_minutes=510,
                   weekdays=days, base_fare_paise=10000)


def test_seat_layout_rejects_invalid_coordinates():
    with pytest.raises(ValidationError):
        SeatLayoutIn(seat_number="A1", row_no=0, col_no=1)


@pytest.mark.parametrize("payment_id,refund_expected", [("original", False), ("extra", True)])
def test_duplicate_event_never_refunds_original_ticket_payment(monkeypatch, payment_id, refund_expected):
    from app.services import booking as service, cancellations
    from app.models import PaymentOrderStatus, SeatInventoryStatus
    db = MagicMock()
    order = NS(id=uuid4(), gateway_order_id="order_1", amount_paise=10000, status=PaymentOrderStatus.PAID)
    original = NS(gateway_payment_id="original", status=PaymentTransactionStatus.CAPTURED)
    extra = NS(gateway_payment_id="extra", status=PaymentTransactionStatus.CAPTURED)
    booking = NS(id=uuid4(), trip_id=uuid4(), pnr="BGM123456", confirmed_payment_id="original",
        booking_status=BookingStatus.CONFIRMED, payment_orders=[order], seats=[NS(released=False)])
    monkeypatch.setattr(service, "lock_trip", lambda *_: NS(status=TripStatus.PUBLISHED))
    monkeypatch.setattr(service, "expire_holds", lambda *_: None)
    monkeypatch.setattr(service, "get_payment_provider", lambda: NS(name="fake"))
    monkeypatch.setattr(service, "_record_transaction", lambda *_: original if payment_id == "original" else extra)
    db.execute.return_value.scalars.return_value.all.side_effect = [[original, extra], [NS(status=SeatInventoryStatus.BOOKED)]]
    refund = MagicMock()
    monkeypatch.setattr(cancellations, "queue_exception_refund", refund)
    service.confirm_paid_booking(db, booking, {"id": payment_id, "order_id": "order_1", "amount": 10000, "status": "captured"})
    assert refund.called == refund_expected
    assert booking.confirmed_payment_id == "original"


def test_processing_refund_is_not_reported_as_completed():
    from app.models import RefundStatus, CancellationStatus
    from app.services.cancellations import apply_refund_result
    db = MagicMock()
    booking = NS(booking_status=BookingStatus.REFUND_PENDING)
    request = NS(booking=booking, status=CancellationStatus.PROCESSING)
    refund = NS(cancellation=request, payment_transaction_id=uuid4(), gateway_refund_id=None)
    apply_refund_result(db, refund, {"id": "refund_1", "status": "pending"})
    assert refund.status == RefundStatus.PROCESSING
    assert request.status == CancellationStatus.PROCESSING
    assert booking.booking_status == BookingStatus.REFUND_PENDING
