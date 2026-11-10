from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import (Booking, BookingStatus, CancellationRequest, CancellationStatus,
    PaymentOrderStatus, PaymentTransaction, PaymentTransactionStatus, Refund, RefundStatus,
    SeatInventoryStatus, TripSeat, TripStatus)
from app.services.inventory import lock_trip, expire_holds
from app.services.payments import get_payment_provider
from app.services.time_utils import as_utc


def estimate_refund(booking: Booking) -> dict:
    policy = booking.policy_snapshot
    if policy is None and booking.trip.cancellation_policy:
        p = booking.trip.cancellation_policy
        policy = {"rules": p.rules, "version": p.version, "disclaimer": p.disclaimer}
    policy = policy or {"rules": {}, "version": "none", "disclaimer": "No refund policy configured."}
    rules = policy["rules"]
    minutes = (as_utc(booking.trip.departure_datetime) - utcnow()).total_seconds() / 60
    cutoff = rules.get("cutoff_minutes", get_settings().cancellation_cutoff_minutes)
    matched = next((r for r in sorted(rules.get("rules", []), key=lambda r: r["min_hours_before_departure"], reverse=True)
                    if minutes / 60 >= r["min_hours_before_departure"]), {"refund_percent": 0})
    eligible = booking.booking_status == BookingStatus.CONFIRMED and minutes > cutoff
    return {"eligible": eligible, "estimated_refund_paise": booking.total_amount_paise * matched["refund_percent"] // 100 if eligible else 0,
            "policy_version": policy["version"], "disclaimer": policy["disclaimer"],
            "breakdown": {"hours_before_departure": round(minutes / 60, 2), "refund_percent": matched["refund_percent"], "cutoff_minutes": cutoff}}


def _release_seats(db, booking):
    for seat in db.execute(select(TripSeat).where(TripSeat.booking_id == booking.id).with_for_update()).scalars():
        seat.status = SeatInventoryStatus.AVAILABLE
        seat.booking_id = seat.hold_id = None
    for seat in booking.seats:
        seat.released = True


def request_cancellation(db: Session, booking: Booking, requested_by: str, reason: str, *, operator_cancel=False):
    lock_trip(db, booking.trip_id)
    db.refresh(booking)
    if booking.booking_status != BookingStatus.CONFIRMED and not (operator_cancel and booking.pnr):
        raise ConflictError("Only confirmed bookings can be cancelled")
    estimate = estimate_refund(booking)
    if not operator_cancel and not estimate["eligible"]:
        raise ConflictError("Customer cancellation cutoff has passed")
    if operator_cancel:
        estimate.update(estimated_refund_paise=booking.total_amount_paise, eligible=True, policy_version="operator-full-refund")
    request = CancellationRequest(booking_id=booking.id, requested_by=requested_by, reason=reason,
        estimated_refund_paise=estimate["estimated_refund_paise"], status=CancellationStatus.PROCESSING,
        policy_version=estimate["policy_version"], calculation_snapshot=estimate)
    db.add(request)
    db.flush()
    _release_seats(db, booking)
    amount = estimate["estimated_refund_paise"]
    booking.booking_status = BookingStatus.REFUND_PENDING if amount else BookingStatus.CANCELLED
    if amount:
        captured = next((t for o in booking.payment_orders for t in o.transactions
                         if t.status == PaymentTransactionStatus.CAPTURED and
                         (not booking.confirmed_payment_id or t.gateway_payment_id == booking.confirmed_payment_id)), None)
        if not captured:
            raise ConflictError("No captured payment exists to refund")
        db.add(Refund(cancellation_request_id=request.id, payment_transaction_id=captured.id,
                      amount_paise=amount, status=RefundStatus.REQUESTED))
    else:
        request.status = CancellationStatus.COMPLETED
    from app.services.notifications import enqueue
    enqueue(db, booking, "cancelled", "Your departure was cancelled by the operator. A full refund is queued." if operator_cancel
            else f"Your booking was cancelled. Refund queued: INR {amount / 100:.2f}.")
    db.flush()
    return request


def queue_exception_refund(db, booking, txn, reason):
    if db.execute(select(Refund.id).where(Refund.payment_transaction_id == txn.id)).first():
        return
    request = CancellationRequest(booking_id=booking.id, requested_by="system", reason=reason,
        estimated_refund_paise=txn.amount_paise, status=CancellationStatus.PROCESSING,
        policy_version="payment-exception", calculation_snapshot={"exception": True})
    db.add(request)
    db.flush()
    db.add(Refund(cancellation_request_id=request.id, payment_transaction_id=txn.id,
                  amount_paise=txn.amount_paise, status=RefundStatus.REQUESTED))
    from app.services.notifications import enqueue
    enqueue(db, booking, "refund_queued", f"{reason}. A refund of INR {txn.amount_paise / 100:.2f} has been queued.", suffix=str(txn.id))
    db.flush()


def apply_refund_result(db, refund, result):
    request = refund.cancellation
    booking = request.booking
    txn = db.get(PaymentTransaction, refund.payment_transaction_id)
    refund.gateway_refund_id = result.get("id") or refund.gateway_refund_id
    status = result.get("status")
    if status == "processed":
        refund.status = RefundStatus.PROCESSED
        request.status = CancellationStatus.COMPLETED
        if not request.calculation_snapshot.get("exception"):
            booking.booking_status = BookingStatus.REFUNDED
            txn.order.status = PaymentOrderStatus.REFUNDED if refund.amount_paise == txn.order.amount_paise else PaymentOrderStatus.PARTIALLY_REFUNDED
        if refund.amount_paise == txn.amount_paise:
            txn.status = PaymentTransactionStatus.REFUNDED
        from app.services.notifications import enqueue
        enqueue(db, booking, "refund_processed", f"Your refund of INR {refund.amount_paise / 100:.2f} has been processed.", suffix=str(refund.id))
    elif status == "failed":
        refund.status = RefundStatus.FAILED
        request.status = CancellationStatus.FAILED
    else:
        refund.status = RefundStatus.PROCESSING
        request.status = CancellationStatus.PROCESSING


def admin_retry_refund(db: Session, refund_id) -> Refund:
    refund = db.get(Refund, refund_id)
    if not refund:
        raise NotFoundError("Refund not found")
    lock_trip(db, refund.cancellation.booking.trip_id)
    db.refresh(refund)
    if refund.status == RefundStatus.PROCESSED:
        return refund
    txn = db.get(PaymentTransaction, refund.payment_transaction_id)
    if refund.cancellation.booking.channel != "online":
        raise ConflictError("Record the offline refund after returning the money to the customer")
    provider = get_payment_provider()
    try:
        result = provider.fetch_refund(refund.gateway_refund_id) if refund.gateway_refund_id else provider.refund(
            txn.gateway_payment_id, refund.amount_paise, str(refund.id))
        apply_refund_result(db, refund, result)
    except Exception:
        refund.status = RefundStatus.FAILED
        refund.cancellation.status = CancellationStatus.FAILED
    return refund


def cancel_trip_and_bookings(db: Session, trip) -> list[Booking]:
    trip = lock_trip(db, trip.id)
    if trip.status in {TripStatus.CANCELLED, TripStatus.COMPLETED}:
        raise ConflictError("Trip is already cancelled or completed")
    expire_holds(db, trip.id)
    trip.status = TripStatus.CANCELLED
    db.flush()
    affected = []
    from app.services.booking import load_booking
    for booking in db.execute(select(Booking).where(Booking.trip_id == trip.id)).scalars():
        full = load_booking(db, booking.id)
        if full.booking_status in {BookingStatus.CONFIRMED, BookingStatus.EXCEPTION} and full.pnr:
            request_cancellation(db, full, "admin", "Operator cancelled the trip", operator_cancel=True)
            affected.append(full)
        elif full.booking_status == BookingStatus.PENDING_PAYMENT:
            _release_seats(db, full)
            full.booking_status = BookingStatus.CANCELLED
    for seat in db.execute(select(TripSeat).where(TripSeat.trip_id == trip.id, TripSeat.status == SeatInventoryStatus.HELD)).scalars():
        seat.status = SeatInventoryStatus.AVAILABLE
        seat.hold_id = seat.booking_id = None
    db.flush()
    return affected
