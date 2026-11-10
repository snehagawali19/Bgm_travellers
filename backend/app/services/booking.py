from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, PaymentError
from app.core.security import utcnow
from app.models import (
    Booking,
    BookingSeat,
    BookingStatus,
    BusSeat,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentTransaction,
    PaymentTransactionStatus,
    SeatHold,
    SeatInventoryStatus,
    TripSeat,
    TripStatus,
    WebhookEvent,
)
from app.schemas import BookingCreateIn, PaymentOrderOut, StopOut
from app.services.inventory import expire_holds, get_valid_hold, release_hold_seats, lock_trip
from app.services.payments import get_payment_provider
from app.services.tickets import generate_access_token, generate_pnr, generate_public_reference, verification_payload
from app.services.trips import load_trip, to_trip_card

logger = logging.getLogger(__name__)


def _booking_seats_payload(booking: Booking) -> list[dict]:
    return [
        {
            "seat_id": str(item.bus_seat_id),
            "seat_number": item.bus_seat.seat_number,
            "passenger_name": item.passenger_name,
            "passenger_age": item.passenger_age,
            "passenger_gender": item.passenger_gender,
            "fare_paise": item.fare_snapshot_paise,
            "id": str(item.id),
            "checked_in_at": item.checked_in_at,
        }
        for item in booking.seats
        if not item.released
    ]


def serialize_booking(db: Session, booking: Booking, include_secrets: bool = False) -> dict:
    trip = load_trip(db, booking.trip_id)
    card = to_trip_card(db, trip)
    payment = None
    order = booking.payment_orders[-1] if booking.payment_orders else None
    if order and booking.booking_status == BookingStatus.PENDING_PAYMENT:
        provider = get_payment_provider()
        payment = PaymentOrderOut(
            provider=provider.name,
            key_id=provider.key_id,
            order_id=order.gateway_order_id,
            amount_paise=order.amount_paise,
            currency=order.currency,
            booking_public_reference=booking.public_reference,
            access_token=booking.access_token,
        )
    policy = trip.cancellation_policy
    return {
        "public_reference": booking.public_reference,
        "pnr": booking.pnr,
        "status": booking.booking_status.value,
        "channel": booking.channel,
        "offline_method": booking.offline_method,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "customer_phone": booking.customer_phone,
        "total_amount_paise": booking.total_amount_paise,
        "trip": card,
        "seats": _booking_seats_payload(booking),
        "pickup_stop": booking.pickup_snapshot or (StopOut.model_validate(booking.pickup_stop) if booking.pickup_stop else None),
        "dropoff_stop": booking.dropoff_snapshot or (StopOut.model_validate(booking.dropoff_stop) if booking.dropoff_stop else None),
        "access_token": booking.access_token if include_secrets else None,
        "verification_code": booking.verification_code if booking.booking_status in {BookingStatus.CONFIRMED, BookingStatus.EXCEPTION} and booking.pnr else None,
        "exception_reason": booking.exception_reason,
        "payment": payment,
        "cancellation_disclaimer": booking.policy_snapshot.get("disclaimer") if booking.policy_snapshot else (policy.disclaimer if policy else None),
        "created_at": booking.created_at,
    }


def create_booking(db: Session, payload: BookingCreateIn, customer_user_id: UUID | None = None, *, offline: bool = False) -> Booking:
    hold = get_valid_hold(db, payload.hold_token)
    trip = load_trip(db, hold.trip_id)
    if trip.status != TripStatus.PUBLISHED:
        raise ConflictError("Trip is not open for booking")
    if trip.departure_datetime - timedelta(minutes=trip.booking_cutoff_minutes) <= utcnow():
        raise ConflictError("Booking cutoff has passed")

    hold_seat_ids = {item.bus_seat_id for item in hold.seats}
    passenger_seat_ids = {item.seat_id for item in payload.passengers}
    if hold_seat_ids != passenger_seat_ids or len(passenger_seat_ids) != len(payload.passengers):
        raise ConflictError("Passenger list must match the held seats")

    pickup = next((stop for stop in trip.route.stops if stop.id == payload.pickup_stop_id and stop.pickup_allowed and stop.active), None)
    dropoff = next((stop for stop in trip.route.stops if stop.id == payload.dropoff_stop_id and stop.dropoff_allowed and stop.active), None)
    if not pickup or not dropoff or pickup.display_order >= dropoff.display_order:
        raise ConflictError("Invalid boarding or dropping point")

    fare = hold.fare_paise if hold.fare_paise is not None else trip.base_fare_paise
    total = fare * len(payload.passengers)
    booking = Booking(
        public_reference=generate_public_reference(),
        trip_id=trip.id,
        customer_user_id=customer_user_id,
        customer_name=payload.customer_name,
        customer_email=str(payload.customer_email).lower(),
        customer_phone=payload.customer_phone,
        pickup_stop_id=payload.pickup_stop_id,
        dropoff_stop_id=payload.dropoff_stop_id,
        total_amount_paise=total,
        booking_status=BookingStatus.PENDING_PAYMENT,
        access_token=generate_access_token(),
        hold_id=hold.id,
        policy_snapshot={"version": trip.cancellation_policy.version, "rules": trip.cancellation_policy.rules,
                         "disclaimer": trip.cancellation_policy.disclaimer} if trip.cancellation_policy else None,
        pickup_snapshot=StopOut.model_validate(pickup).model_copy(update={"stop_datetime": trip.departure_datetime + timedelta(minutes=pickup.offset_minutes)}).model_dump(mode="json"),
        dropoff_snapshot=StopOut.model_validate(dropoff).model_copy(update={"stop_datetime": trip.departure_datetime + timedelta(minutes=dropoff.offset_minutes)}).model_dump(mode="json"),
    )
    db.add(booking)
    db.flush()
    hold.booking_id = booking.id
    for passenger in payload.passengers:
        db.add(
            BookingSeat(
                booking_id=booking.id,
                trip_id=trip.id,
                bus_seat_id=passenger.seat_id,
                passenger_name=passenger.name,
                passenger_age=passenger.age,
                passenger_gender=passenger.gender,
                fare_snapshot_paise=fare,
            )
        )
        inventory = db.execute(
            select(TripSeat).where(TripSeat.trip_id == trip.id, TripSeat.bus_seat_id == passenger.seat_id)
        ).scalar_one()
        inventory.booking_id = booking.id

    if offline:
        db.flush()
        return load_booking(db, booking.id)

    provider = get_payment_provider()
    order = provider.create_order(
        amount_paise=total,
        receipt=booking.public_reference,
        notes={"booking": booking.public_reference, "trip": str(trip.id)},
    )
    db.add(
        PaymentOrder(
            booking_id=booking.id,
            gateway_order_id=order["id"],
            amount_paise=total,
            currency="INR",
            status=PaymentOrderStatus.CREATED,
        )
    )
    db.flush()
    return load_booking(db, booking.id)


def load_booking(db: Session, booking_id: UUID | None = None, public_reference: str | None = None) -> Booking:
    query = select(Booking).options(
        joinedload(Booking.pickup_stop),
        joinedload(Booking.dropoff_stop),
        selectinload(Booking.seats).joinedload(BookingSeat.bus_seat),
        selectinload(Booking.payment_orders).selectinload(PaymentOrder.transactions),
        selectinload(Booking.cancellations),
    )
    if booking_id:
        query = query.where(Booking.id == booking_id)
    elif public_reference:
        query = query.where(Booking.public_reference == public_reference)
    booking = db.execute(query).unique().scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")
    return booking


def assert_booking_access(booking: Booking, access_token: str | None, phone: str | None = None) -> None:
    if access_token and access_token == booking.access_token:
        return
    if phone and phone[-10:] == booking.customer_phone[-10:] and booking.pnr:
        return
    raise ForbiddenError("You do not have access to this booking")


def lookup_booking(db: Session, pnr: str, phone: str) -> Booking:
    digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
    booking = db.execute(select(Booking).where(Booking.pnr == pnr.upper())).scalar_one_or_none()
    if not booking or booking.customer_phone[-10:] != digits:
        raise NotFoundError("No booking matched that PNR and mobile number")
    return load_booking(db, booking.id)


def _record_transaction(db: Session, order: PaymentOrder, payment: dict) -> PaymentTransaction:
    existing = db.execute(
        select(PaymentTransaction).where(PaymentTransaction.gateway_payment_id == payment["id"])
    ).scalar_one_or_none()
    if existing:
        if existing.payment_order_id != order.id:
            raise PaymentError("Payment belongs to another order")
        if payment.get("status") == "captured" and existing.status != PaymentTransactionStatus.REFUNDED:
            existing.status = PaymentTransactionStatus.CAPTURED
        return existing
    status_map = {
        "captured": PaymentTransactionStatus.CAPTURED,
        "authorized": PaymentTransactionStatus.AUTHORIZED,
        "failed": PaymentTransactionStatus.FAILED,
        "refunded": PaymentTransactionStatus.REFUNDED,
    }
    txn = PaymentTransaction(
        payment_order_id=order.id,
        gateway_payment_id=payment["id"],
        amount_paise=int(payment.get("amount") or order.amount_paise),
        status=status_map.get(payment.get("status", ""), PaymentTransactionStatus.AUTHORIZED),
        method=payment.get("method"),
        raw_payload={"status": payment.get("status"), "id": payment.get("id"), "method": payment.get("method")},
    )
    db.add(txn)
    db.flush()
    return txn


def confirm_paid_booking(db: Session, booking: Booking, payment: dict) -> Booking:
    trip = lock_trip(db, booking.trip_id)
    db.refresh(booking)
    expire_holds(db, booking.trip_id)
    order = next((item for item in booking.payment_orders if item.gateway_order_id == payment.get("order_id")), None)
    if not order and get_payment_provider().name == "fake" and not payment.get("order_id"):
        order = booking.payment_orders[-1] if booking.payment_orders else None
    if not order:
        raise PaymentError("Payment order missing")
    fake = get_payment_provider().name == "fake"
    if not fake and (payment.get("currency") != "INR" or payment.get("amount") != order.amount_paise):
        raise PaymentError("Payment amount or currency does not match the order")
    if fake and payment.get("amount", 0) not in {0, order.amount_paise}:
        raise PaymentError("Payment amount does not match the order")
    txn = _record_transaction(db, order, payment)

    db.flush()
    captured_txns = db.execute(select(PaymentTransaction).where(
        PaymentTransaction.payment_order_id == order.id,
        PaymentTransaction.status == PaymentTransactionStatus.CAPTURED).order_by(
        PaymentTransaction.created_at, PaymentTransaction.id)).scalars().all()
    if booking.pnr and not booking.confirmed_payment_id and captured_txns:
        booking.confirmed_payment_id = captured_txns[0].gateway_payment_id
    extra_captured = bool(booking.confirmed_payment_id and txn.gateway_payment_id != booking.confirmed_payment_id)

    # Retries and old webhooks must never revive a cancelled reservation.
    if booking.booking_status in {BookingStatus.CANCELLED, BookingStatus.REFUNDED, BookingStatus.REFUND_PENDING}:
        if txn.status == PaymentTransactionStatus.CAPTURED:
            from app.services.cancellations import queue_exception_refund
            queue_exception_refund(db, booking, txn, "Payment received after cancellation")
        return booking

    if txn.status != PaymentTransactionStatus.CAPTURED:
        if txn.status == PaymentTransactionStatus.FAILED:
            if order.status != PaymentOrderStatus.PAID:
                order.status = PaymentOrderStatus.FAILED
        return booking

    inventory = (
        db.execute(
            select(TripSeat)
            .where(TripSeat.trip_id == booking.trip_id, TripSeat.booking_id == booking.id)
            .with_for_update()
        )
        .scalars()
        .all()
    )
    seats_still_held = len(inventory) == len([s for s in booking.seats if not s.released]) and bool(inventory) and all(
        seat.status in {SeatInventoryStatus.HELD, SeatInventoryStatus.BOOKED} for seat in inventory
    )

    if booking.pnr and seats_still_held:
        order.status = PaymentOrderStatus.PAID
        if extra_captured:
            booking.exception_reason = "Duplicate captured payment requires refund reconciliation"
            booking.booking_status = BookingStatus.EXCEPTION
            from app.services.cancellations import queue_exception_refund
            queue_exception_refund(db, booking, txn, "Duplicate captured payment")
        return booking

    if not seats_still_held or trip.status not in {TripStatus.PUBLISHED, TripStatus.CLOSED}:
        booking.booking_status = BookingStatus.EXCEPTION
        booking.exception_reason = "Payment captured after seat hold expired; ticket not issued"
        order.status = PaymentOrderStatus.PAID
        logger.warning("exception_booking_unsecured_seat ref=%s", booking.public_reference)
        from app.services.cancellations import queue_exception_refund
        queue_exception_refund(db, booking, txn, "Payment captured after hold expiry")
        return booking

    for seat in inventory:
        seat.status = SeatInventoryStatus.BOOKED
        seat.hold_id = None
    booking.booking_status = BookingStatus.CONFIRMED
    booking.pnr = booking.pnr or generate_pnr(db)
    booking.confirmed_payment_id = txn.gateway_payment_id
    booking.verification_code = verification_payload(booking)
    order.status = PaymentOrderStatus.PAID
    from app.services.notifications import enqueue
    enqueue(db, booking, "confirmed", "Your booking is confirmed. Please arrive 15 minutes before your boarding time.")
    if extra_captured:
        booking.exception_reason = "Duplicate captured payment requires refund reconciliation"
        booking.booking_status = BookingStatus.EXCEPTION
    return booking


def verify_checkout_payment(db: Session, public_reference: str, order_id: str, payment_id: str, signature: str) -> Booking:
    booking = load_booking(db, public_reference=public_reference)
    order = next((item for item in booking.payment_orders if item.gateway_order_id == order_id), None)
    if not order:
        raise PaymentError("Unknown payment order")
    provider = get_payment_provider()
    if not provider.verify_checkout_signature(order_id, payment_id, signature):
        raise PaymentError("Invalid payment signature")
    payment = provider.fetch_payment(payment_id)
    if int(payment.get("amount") or order.amount_paise) and int(payment.get("amount") or 0) not in {0, order.amount_paise}:
        raise PaymentError("Paid amount does not match booking total")
    confirm_paid_booking(db, booking, payment)
    db.flush()
    return load_booking(db, booking.id)


def process_webhook(db: Session, provider_name: str, event_id: str, event_type: str, payload: dict) -> None:
    event = db.execute(insert(WebhookEvent).values(provider=provider_name, event_id=event_id, event_type=event_type,
        processed=True, payload={"event": event_type}).on_conflict_do_nothing(
        index_elements=["provider", "event_id"]).returning(WebhookEvent.id)).scalar_one_or_none()
    if event is None:
        return
    if event_type.startswith("refund."):
        from app.models import Refund
        from app.services.cancellations import apply_refund_result
        entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        refund = db.execute(select(Refund).where(Refund.gateway_refund_id == entity.get("id"))).scalar_one_or_none()
        if refund:
            lock_trip(db, refund.cancellation.booking.trip_id)
            if refund.status.value != "processed":
                apply_refund_result(db, refund, entity)
        return
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment.get("order_id")
    if not order_id:
        return
    order = db.execute(select(PaymentOrder).where(PaymentOrder.gateway_order_id == order_id)).scalar_one_or_none()
    if not order:
        return
    booking = load_booking(db, order.booking_id)
    if event_type in {"payment.captured", "payment.authorized", "order.paid"}:
        confirm_paid_booking(db, booking, payment)
    elif event_type == "payment.failed":
        confirm_paid_booking(db, booking, {**payment, "status": "failed"})
    event = db.execute(
        select(WebhookEvent).where(WebhookEvent.provider == provider_name, WebhookEvent.event_id == event_id)
    ).scalar_one()
    event.processed = True


def expire_pending_bookings(db: Session) -> None:
    expire_holds(db)


def reconcile_booking(db, booking):
    if booking.channel != "online":
        return booking
    lock_trip(db, booking.trip_id)
    provider = get_payment_provider()
    for order in booking.payment_orders:
        for payment in provider.order_payments(order.gateway_order_id):
            confirm_paid_booking(db, booking, payment)
    return booking
