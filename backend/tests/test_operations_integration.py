"""PostgreSQL regression coverage for the operational workflows."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError
from app.core.security import utcnow
from app.models import (Booking, BookingStatus, Notification, PaymentTransaction, PaymentTransactionStatus,
    Refund, SeatHold, SeatInventoryStatus, TripSeat, TripStatus)
from app.schemas import BookingCreateIn, CounterBookingIn, SeatLayoutIn, SwapBusIn, GenerateTripsIn
from app.services.booking import create_booking, load_booking, confirm_paid_booking
from app.services.cancellations import cancel_trip_and_bookings
from app.services.inventory import create_hold, expire_holds
from app.services.operations import counter_booking, replace_layout, swap_bus, generate_trips
from app.services.trips import create_trip
from tests.conftest import add_bus, seed_launch, seat_ids
from tests.test_booking_flow import _hold_and_book


def counter_payload(data, count=1):
    trip = data["trip_out"]
    return CounterBookingIn(trip_id=trip.id, request_id=uuid4(), payment_method="cash", customer_name="Counter Customer",
        customer_phone="9876543210", customer_email="counter@example.com",
        pickup_stop_id=next(s.id for s in trip.route.stops if s.pickup_allowed),
        dropoff_stop_id=next(s.id for s in trip.route.stops if s.dropoff_allowed),
        passengers=[{"seat_id": s, "name": "Passenger One", "age": 30, "gender": "male"} for s in seat_ids(data["bus"], count)])


def test_layout_edits_preserve_existing_inventory(client, db):
    data = seed_launch(db)
    before = client.get(f"/api/v1/trips/{data['trip_out'].id}").json()
    replace_layout(db, data["bus"].id, [SeatLayoutIn(seat_number="NEW1", row_no=1, col_no=1)])
    db.commit()
    after = client.get(f"/api/v1/trips/{data['trip_out'].id}").json()
    assert before["seats"] == after["seats"]
    assert after["trip"]["total_seats"] == 40
    new = create_trip(db, route_id=data["outbound"].id, bus_id=data["bus"].id,
        departure_datetime=utcnow() + timedelta(days=10), estimated_arrival_datetime=utcnow() + timedelta(days=10, hours=9),
        base_fare_paise=10000, status=TripStatus.PUBLISHED)
    assert len(new.inventory) == 1
    assert new.inventory[0].bus_seat.seat_number == "NEW1"


def test_checkout_hold_expires_without_background_cleanup(client, db):
    data = seed_launch(db)
    response, seats, _ = _hold_and_book(client, db, data["trip_out"], data["bus"])
    booking = load_booking(db, public_reference=response.json()["public_reference"])
    hold = db.get(SeatHold, booking.hold_id)
    hold.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    replacement = create_hold(db, data["trip_out"].id, [UUID(seats[0])])
    assert replacement.id != hold.id
    assert booking.booking_status == BookingStatus.EXPIRED
    assert all(s.released for s in booking.seats)


def test_atomic_hold_conflict_releases_no_partial_seats(db):
    data = seed_launch(db)
    ids = [UUID(s) for s in seat_ids(data["bus"], 2)]
    create_hold(db, data["trip_out"].id, [ids[1]])
    with pytest.raises(ConflictError):
        create_hold(db, data["trip_out"].id, ids)
    first = db.execute(select(TripSeat).where(TripSeat.trip_id == data["trip_out"].id, TripSeat.bus_seat_id == ids[0])).scalar_one()
    assert first.status == SeatInventoryStatus.AVAILABLE


def test_counter_sale_is_idempotent_and_competes_with_online(db):
    data = seed_launch(db)
    payload = counter_payload(data, count=2)
    booking = counter_booking(db, payload)
    db.commit()
    assert booking.pnr and booking.channel == "counter"
    assert counter_booking(db, payload).id == booking.id
    assert db.query(PaymentTransaction).count() == 1
    with pytest.raises(ConflictError):
        create_hold(db, data["trip_out"].id, [payload.passengers[0].seat_id])
    assert db.query(Notification).count() == 1


def test_online_hold_prevents_counter_sale(db):
    data = seed_launch(db)
    payload = counter_payload(data)
    create_hold(db, payload.trip_id, [payload.passengers[0].seat_id])
    with pytest.raises(ConflictError):
        counter_booking(db, payload)
    assert db.query(Booking).count() == 0


def test_customer_cutoff_and_closed_departure_reject_holds(db):
    data = seed_launch(db)
    trip = data["trip_out"]
    trip.departure_datetime = utcnow() + timedelta(minutes=59)
    db.flush()
    with pytest.raises(ConflictError):
        create_hold(db, trip.id, [UUID(seat_ids(data["bus"])[0])])


def test_operator_cancellation_queues_full_refund_inside_customer_cutoff(db):
    data = seed_launch(db)
    booking = counter_booking(db, counter_payload(data))
    db.commit()
    trip = data["trip_out"]
    trip.departure_datetime = utcnow() + timedelta(minutes=20)
    db.flush()
    cancel_trip_and_bookings(db, trip)
    refund = db.query(Refund).one()
    assert refund.amount_paise == booking.total_amount_paise
    assert booking.booking_status == BookingStatus.REFUND_PENDING
    assert all(s.released for s in booking.seats)


def test_swap_requires_mapping_and_preserves_booking_reference(db):
    data = seed_launch(db)
    booking = counter_booking(db, counter_payload(data))
    db.commit()
    bus = add_bus(db, "KA-22-N-9999", "Replacement", rows=1)
    with pytest.raises(ConflictError):
        swap_bus(db, data["trip_out"].id, SwapBusIn(bus_id=bus.id))
    original_pnr = booking.pnr
    target_id = bus.seats[0].id
    swap_bus(db, data["trip_out"].id, SwapBusIn(bus_id=bus.id, seat_mapping={booking.seats[0].bus_seat_id: target_id}))
    db.commit()
    assert booking.pnr == original_pnr
    assert booking.seats[0].bus_seat_id == target_id
    assert len(data["trip_out"].inventory) == 4


def test_late_payment_queues_refund_without_reserving_resold_seat(client, db):
    data = seed_launch(db)
    response, seats, _ = _hold_and_book(client, db, data["trip_out"], data["bus"])
    booking = load_booking(db, public_reference=response.json()["public_reference"])
    db.get(SeatHold, booking.hold_id).expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    create_hold(db, data["trip_out"].id, [UUID(seats[0])])
    confirm_paid_booking(db, booking, {"id": "pay_late", "order_id": booking.payment_orders[0].gateway_order_id,
        "amount": booking.total_amount_paise, "currency": "INR", "status": "captured"})
    assert booking.pnr is None
    assert booking.booking_status == BookingStatus.EXCEPTION
    assert db.query(Refund).count() == 1


def test_repeated_schedule_generation_is_idempotent(db):
    from app.models import RecurringSchedule
    data = seed_launch(db)
    schedule = RecurringSchedule(name="Daily", active=True, definition={"name": "Daily", "route_id": str(data["outbound"].id),
        "bus_id": str(data["bus"].id), "departure_time": "21:30", "duration_minutes": 510,
        "weekdays": list(range(7)), "base_fare_paise": 89900})
    db.add(schedule)
    db.flush()
    day = (utcnow() + timedelta(days=10)).date()
    payload = GenerateTripsIn(start_date=day, end_date=day + timedelta(days=2))
    assert len(generate_trips(db, schedule.id, payload)) == 3
    assert generate_trips(db, schedule.id, payload) == []


def test_fare_quoted_at_hold_survives_fare_edits(db):
    data = seed_launch(db)
    details = counter_payload(data)
    hold = create_hold(db, details.trip_id, [p.seat_id for p in details.passengers])
    quote = hold.fare_paise
    data["trip_out"].base_fare_paise = quote + 50000
    db.flush()
    booking = create_booking(db, BookingCreateIn.model_validate({**details.model_dump(), "hold_token": hold.token}))
    assert booking.total_amount_paise == quote
    assert booking.seats[0].fare_snapshot_paise == quote


def test_duplicate_capture_replay_refunds_only_extra_payment(client, db):
    data = seed_launch(db)
    response, _, _ = _hold_and_book(client, db, data["trip_out"], data["bus"])
    booking = load_booking(db, public_reference=response.json()["public_reference"])
    order_id = booking.payment_orders[0].gateway_order_id
    for payment_id in ("pay_first", "pay_extra", "pay_first", "pay_extra"):
        confirm_paid_booking(db, booking, {"id": payment_id, "order_id": order_id, "amount": booking.total_amount_paise,
                                         "currency": "INR", "status": "captured"})
        db.commit()
    assert booking.confirmed_payment_id == "pay_first"
    refund = db.query(Refund).one()
    assert db.get(PaymentTransaction, refund.payment_transaction_id).gateway_payment_id == "pay_extra"
