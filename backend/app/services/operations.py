from datetime import datetime, timedelta
import hashlib
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, delete, text

from app.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import (Booking, BookingSeat, BookingStatus, Bus, BusSeat, SeatType, Trip, TripSeat,
    TripStatus, SeatInventoryStatus, PaymentOrder, PaymentOrderStatus, PaymentTransaction,
    PaymentTransactionStatus, RecurringSchedule)
from app.schemas import BookingCreateIn, ScheduleIn
from app.services.inventory import create_hold, lock_trip, expire_holds
from app.services.booking import create_booking, load_booking
from app.services.tickets import generate_pnr, verification_payload
from app.services.trips import create_trip, assert_bus_available
from app.services.notifications import enqueue


def replace_layout(db, bus_id, seats):
    bus = db.execute(select(Bus).where(Bus.id == bus_id).with_for_update()).scalar_one_or_none()
    if not bus:
        raise NotFoundError("Bus not found")
    active = [s for s in seats if s.active]
    if not active or len(active) > 100 or len({s.seat_number for s in active}) != len(active):
        raise ConflictError("Layout needs 1–100 seats with unique labels")
    if len({(s.deck, s.row_no, s.col_no) for s in active}) != len(active):
        raise ConflictError("Two seats cannot share the same position")
    for seat in db.execute(select(BusSeat).where(BusSeat.bus_id == bus_id, BusSeat.active.is_(True))).scalars():
        seat.active = False
    db.flush()
    for item in seats:
        db.add(BusSeat(bus_id=bus_id, **item.model_dump()))
    bus.seat_capacity = len(active)
    db.flush()
    return bus


def generate_trips(db, schedule_id, payload):
    schedule = db.execute(select(RecurringSchedule).where(RecurringSchedule.id == schedule_id).with_for_update()).scalar_one_or_none()
    if not schedule or not schedule.active:
        raise ConflictError("Schedule is not active")
    if not 0 <= (payload.end_date - payload.start_date).days <= 90:
        raise ConflictError("Generate a range of at most 91 days")
    definition = ScheduleIn.model_validate(schedule.definition)
    day = payload.start_date
    created = []
    while day <= payload.end_date:
        if day.weekday() in definition.weekdays and not db.execute(select(Trip.id).where(
                Trip.schedule_id == schedule.id, Trip.service_date == day.isoformat())).first():
            departure = datetime.combine(day, definition.departure_time, ZoneInfo("Asia/Kolkata"))
            if departure <= utcnow():
                raise ConflictError("Cannot generate departures in the past")
            trip = create_trip(db, route_id=definition.route_id, bus_id=definition.bus_id,
                departure_datetime=departure, estimated_arrival_datetime=departure + timedelta(minutes=definition.duration_minutes),
                base_fare_paise=definition.base_fare_paise, booking_cutoff_minutes=definition.booking_cutoff_minutes,
                cancellation_policy_id=definition.cancellation_policy_id, schedule_id=schedule.id, service_date=day.isoformat(),
                status=TripStatus.PUBLISHED if payload.publish else TripStatus.DRAFT)
            created.append(str(trip.id))
        day += timedelta(days=1)
    return created


def counter_booking(db, payload):
    # Stable request key prevents a double cash sale when a staff request is retried.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": str(payload.request_id)})
    existing = db.execute(select(Booking).where(Booking.staff_request_id == str(payload.request_id))).scalar_one_or_none()
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    if existing:
        previous = next((t.raw_payload.get("request_fingerprint") for o in existing.payment_orders for t in o.transactions), None)
        if previous != fingerprint:
            raise ConflictError("Request key was already used for a different booking")
        return load_booking(db, existing.id)
    if payload.payment_method not in get_settings().offline_payment_methods:
        raise ConflictError("This offline payment method is not approved")
    if payload.payment_method != "cash" and not payload.payment_reference.strip():
        raise ConflictError("Enter the offline payment reference")
    hold = create_hold(db, payload.trip_id, [p.seat_id for p in payload.passengers])
    details = BookingCreateIn.model_validate({**payload.model_dump(), "hold_token": hold.token})
    booking = create_booking(db, details, offline=True)
    booking.channel = payload.channel
    booking.offline_method = payload.payment_method
    booking.staff_request_id = str(payload.request_id)
    booking.booking_status = BookingStatus.CONFIRMED
    booking.pnr = generate_pnr(db)
    booking.confirmed_payment_id = f"offline_{payload.request_id}"
    booking.verification_code = verification_payload(booking)
    order = PaymentOrder(booking_id=booking.id, gateway_order_id=f"offline_{payload.request_id}",
        amount_paise=booking.total_amount_paise, currency="INR", status=PaymentOrderStatus.PAID)
    db.add(order)
    db.flush()
    db.add(PaymentTransaction(payment_order_id=order.id, gateway_payment_id=f"offline_{payload.request_id}",
        amount_paise=booking.total_amount_paise, status=PaymentTransactionStatus.CAPTURED,
        method=payload.payment_method, raw_payload={"reference": payload.payment_reference, "request_fingerprint": fingerprint}))
    for seat in db.execute(select(TripSeat).where(TripSeat.booking_id == booking.id)).scalars():
        seat.status = SeatInventoryStatus.BOOKED
        seat.hold_id = None
    enqueue(db, booking, "confirmed", "Your booking is confirmed. Please arrive 15 minutes before boarding.")
    db.flush()
    return booking


def swap_bus(db, trip_id, payload):
    trip = lock_trip(db, trip_id)
    if trip.status in {TripStatus.CANCELLED, TripStatus.COMPLETED}:
        raise ConflictError("Cannot change a cancelled or completed trip")
    expire_holds(db, trip_id)
    assert_bus_available(db, payload.bus_id, trip.departure_datetime, trip.estimated_arrival_datetime, trip.id)
    inventory = db.execute(select(TripSeat).where(TripSeat.trip_id == trip_id)).scalars().all()
    if any(s.status == SeatInventoryStatus.HELD for s in inventory):
        raise ConflictError("Wait for active checkouts to finish or expire before swapping buses")
    target = db.execute(select(BusSeat).where(BusSeat.bus_id == payload.bus_id, BusSeat.active.is_(True))).scalars().all()
    if not target:
        raise ConflictError("Replacement bus needs a seat layout")
    target_ids = {s.id for s in target}
    required = {s.bus_seat_id for s in inventory if s.status in {SeatInventoryStatus.BOOKED, SeatInventoryStatus.BLOCKED}}
    mapping = payload.seat_mapping
    if set(mapping) != required or len(set(mapping.values())) != len(mapping) or not set(mapping.values()) <= target_ids:
        raise ConflictError("Map every booked and blocked seat to a distinct seat on the replacement bus before applying")
    booked_seats = db.execute(select(BookingSeat).where(BookingSeat.trip_id == trip_id, BookingSeat.released.is_(False))).scalars().all()
    # Release the partial unique index during a permutation, in this transaction only.
    for seat in booked_seats:
        seat.released = True
    db.flush()
    for seat in booked_seats:
        seat.bus_seat_id = mapping[seat.bus_seat_id]
        seat.released = False
    db.flush()
    saved = {mapping[s.bus_seat_id]: (s.status, s.booking_id) for s in inventory if s.bus_seat_id in mapping}
    db.execute(delete(TripSeat).where(TripSeat.trip_id == trip_id))
    for seat in target:
        state, booking_id = saved.get(seat.id, (SeatInventoryStatus.AVAILABLE, None))
        db.add(TripSeat(trip_id=trip_id, bus_seat_id=seat.id, status=state, booking_id=booking_id))
    trip.bus_id = payload.bus_id
    db.flush()
    db.expire(trip, ["inventory", "bus"])
    for booking_id in {s.booking_id for s in booked_seats}:
        booking = load_booking(db, booking_id)
        for seat in booking.seats:
            db.expire(seat, ["bus_seat"])
        enqueue(db, booking, "trip_changed", "Your bus or seat assignment changed. Please review your updated ticket.", suffix=uuid4().hex)
    return trip
