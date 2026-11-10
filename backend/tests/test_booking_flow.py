from __future__ import annotations

from datetime import timedelta

from zoneinfo import ZoneInfo

from app.core.security import utcnow
from app.models import Booking, BookingStatus, SeatHold, SeatInventoryStatus, TripSeat
from app.services.inventory import expire_holds
from app.services.payments import fake_signature, fake_webhook_signature
from tests.conftest import add_bus, add_city, add_route, add_trip, seat_ids, seed_launch


def _hold_and_book(client, db, trip, bus, name="Ravi Kumar", phone="9876543210"):
    seats = seat_ids(bus, 1)
    pickup = next(s for s in trip.route.stops if s.pickup_allowed)
    drop = next(s for s in trip.route.stops if s.dropoff_allowed)
    hold = client.post("/api/v1/holds", json={"trip_id": str(trip.id), "seat_ids": seats}).json()
    booking = client.post(
        "/api/v1/bookings",
        json={
            "hold_token": hold["hold_token"],
            "customer_name": name,
            "customer_email": f"{phone}@example.com",
            "customer_phone": phone,
            "pickup_stop_id": str(pickup.id),
            "dropoff_stop_id": str(drop.id),
            "passengers": [{"name": name, "age": 32, "gender": "male", "seat_id": seats[0]}],
        },
    )
    return booking, seats, hold


def test_search_both_directions_and_empty_date(client, db):
    data = seed_launch(db)
    empty = client.get(
        "/api/v1/trips/search",
        params={
            "origin_city_id": str(data["belgaum"].id),
            "destination_city_id": str(data["bengaluru"].id),
            "travel_date": "2099-01-01",
            "passengers": 1,
        },
    )
    assert empty.status_code == 200
    assert empty.json() == []

    out = client.get(
        "/api/v1/trips/search",
        params={
            "origin_city_id": str(data["belgaum"].id),
            "destination_city_id": str(data["bengaluru"].id),
            "travel_date": data["trip_out"].departure_datetime.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat(),
            "passengers": 1,
        },
    ).json()
    inbound = client.get(
        "/api/v1/trips/search",
        params={
            "origin_city_id": str(data["bengaluru"].id),
            "destination_city_id": str(data["belgaum"].id),
            "travel_date": data["trip_in"].departure_datetime.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat(),
            "passengers": 1,
        },
    ).json()
    assert len(out) == 1
    assert len(inbound) == 1
    assert out[0]["origin_name"] == "Belgaum"
    assert inbound[0]["origin_name"] == "Bengaluru"


def test_seat_hold_expiry_and_conflict(client, db):
    data = seed_launch(db)
    trip, bus = data["trip_out"], data["bus"]
    seats = seat_ids(bus, 1)
    first = client.post("/api/v1/holds", json={"trip_id": str(trip.id), "seat_ids": seats})
    assert first.status_code == 200
    second = client.post("/api/v1/holds", json={"trip_id": str(trip.id), "seat_ids": seats})
    assert second.status_code == 409

    hold = db.query(SeatHold).one()
    hold.expires_at = utcnow() - timedelta(seconds=5)
    db.flush()
    expire_holds(db, trip.id)
    inventory = db.query(TripSeat).filter(TripSeat.bus_seat_id == seats[0]).first()
    # compare as string because of UUID
    inventory = db.query(TripSeat).filter(TripSeat.trip_id == trip.id).all()
    held = [row for row in inventory if str(row.bus_seat_id) == seats[0]][0]
    assert held.status == SeatInventoryStatus.AVAILABLE

    retry = client.post("/api/v1/holds", json={"trip_id": str(trip.id), "seat_ids": seats})
    assert retry.status_code == 200


def test_payment_success_failure_and_ticket(client, db):
    data = seed_launch(db)
    trip, bus = data["trip_out"], data["bus"]
    booking_res, _, hold = _hold_and_book(client, db, trip, bus)
    assert booking_res.status_code == 200
    booking = booking_res.json()
    assert booking["status"] == "pending_payment"
    assert booking["pnr"] is None

    failed = client.post(
        "/api/v1/payments/verify",
        json={
            "public_reference": booking["public_reference"],
            "gateway_order_id": booking["payment"]["order_id"],
            "gateway_payment_id": "pay_fail_1",
            "gateway_signature": "test_signature",
        },
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "pending_payment"

    delayed = client.post(
        "/api/v1/payments/verify",
        json={
            "public_reference": booking["public_reference"],
            "gateway_order_id": booking["payment"]["order_id"],
            "gateway_payment_id": "pay_pending_1",
            "gateway_signature": "test_signature",
        },
    )
    assert delayed.json()["status"] == "pending_payment"

    order_id = booking["payment"]["order_id"]
    pay_id = "pay_ok_1"
    success = client.post(
        "/api/v1/payments/verify",
        json={
            "public_reference": booking["public_reference"],
            "gateway_order_id": order_id,
            "gateway_payment_id": pay_id,
            "gateway_signature": fake_signature(order_id, pay_id),
        },
    )
    body = success.json()
    assert success.status_code == 200
    assert body["status"] == "confirmed"
    assert body["pnr"].startswith("BGM")
    assert body["verification_code"]


def test_duplicate_webhook_and_duplicate_capture(client, db):
    data = seed_launch(db)
    trip, bus = data["trip_out"], data["bus"]
    booking_res, _, _ = _hold_and_book(client, db, trip, bus, phone="9876500001")
    booking = booking_res.json()
    order_id = booking["payment"]["order_id"]
    payload = {
        "id": "evt_1",
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_ok_dup", "order_id": order_id, "status": "captured", "amount": 89900}}},
    }
    headers = {"X-Razorpay-Signature": "test_webhook"}
    first = client.post("/api/v1/payments/webhook", json=payload, headers=headers)
    second = client.post("/api/v1/payments/webhook", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    confirmed = db.query(Booking).filter(Booking.public_reference == booking["public_reference"]).one()
    assert confirmed.booking_status == BookingStatus.CONFIRMED

    payload2 = {
        "id": "evt_2",
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"id": "pay_ok_dup2", "order_id": order_id, "status": "captured", "amount": 89900}}
        },
    }
    client.post("/api/v1/payments/webhook", json=payload2, headers=headers)
    again = db.query(Booking).filter(Booking.public_reference == booking["public_reference"]).one()
    assert again.booking_status == BookingStatus.EXCEPTION
    assert "Duplicate captured payment" in (again.exception_reason or "")


def test_refund_and_booking_privacy(client, db):
    data = seed_launch(db)
    trip, bus = data["trip_out"], data["bus"]
    booking_res, _, _ = _hold_and_book(client, db, trip, bus, phone="9876500002")
    booking = booking_res.json()
    order_id = booking["payment"]["order_id"]
    client.post(
        "/api/v1/payments/verify",
        json={
            "public_reference": booking["public_reference"],
            "gateway_order_id": order_id,
            "gateway_payment_id": "pay_ok_ref",
            "gateway_signature": "test_signature",
        },
    )
    denied = client.get(f"/api/v1/bookings/{booking['public_reference']}")
    assert denied.status_code == 403
    ok = client.get(
        f"/api/v1/bookings/{booking['public_reference']}",
        params={"access_token": booking["access_token"]},
    )
    assert ok.status_code == 200
    cancel = client.post(
        f"/api/v1/bookings/{booking['public_reference']}/cancel",
        params={"access_token": booking["access_token"]},
        json={"reason": "change of plans"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] in {"refunded", "refund_pending", "cancelled"}


def test_admin_auth_and_bus_conflict(client, db):
    data = seed_launch(db)
    denied = client.get("/api/v1/admin/bookings")
    assert denied.status_code in {401, 403}
    login = client.post("/api/v1/admin/auth/login", json={"email": "admin@bgmtravels.in", "password": "ChangeMe_Admin123!"})
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    listings = client.get("/api/v1/admin/trips")
    assert listings.status_code == 200
    trip = data["trip_out"]
    conflict = client.post(
        "/api/v1/admin/trips",
        headers={"X-CSRF-Token": csrf},
        json={
            "route_id": str(data["inbound"].id),
            "bus_id": str(data["bus"].id),
            "departure_datetime": trip.departure_datetime.isoformat(),
            "estimated_arrival_datetime": trip.estimated_arrival_datetime.isoformat(),
            "base_fare_paise": 99900,
            "status": "published",
        },
    )
    assert conflict.status_code == 409


def test_second_bus_and_new_city_do_not_break_existing_bookings(client, db):
    data = seed_launch(db)
    trip, bus = data["trip_out"], data["bus"]
    booking_res, _, _ = _hold_and_book(client, db, trip, bus, phone="9876500003")
    booking = booking_res.json()
    client.post(
        "/api/v1/payments/verify",
        json={
            "public_reference": booking["public_reference"],
            "gateway_order_id": booking["payment"]["order_id"],
            "gateway_payment_id": "pay_ok_exp",
            "gateway_signature": "test_signature",
        },
    )
    original_pnr = client.get(
        f"/api/v1/bookings/{booking['public_reference']}",
        params={"access_token": booking["access_token"]},
    ).json()["pnr"]

    bus2 = add_bus(db, "KA-22-N-2202", "BGM Comfort 02", rows=6)
    later = add_trip(db, data["outbound"], bus2, hours_ahead=120, fare=109900)
    mumbai = add_city(db, "Mumbai", "mumbai", ["Bombay"])
    route = add_route(db, data["bengaluru"], mumbai)
    add_trip(db, route, bus2, hours_ahead=160, fare=149900)

    cities = client.get("/api/v1/cities").json()
    names = {city["name"] for city in cities}
    assert "Mumbai" in names
    assert "Belgaum" in names

    still = client.get(
        f"/api/v1/bookings/{booking['public_reference']}",
        params={"access_token": booking["access_token"]},
    ).json()
    assert still["pnr"] == original_pnr
    assert still["status"] == "confirmed"

    seats_bus2 = seat_ids(bus2, 1)
    hold = client.post("/api/v1/holds", json={"trip_id": str(later.id), "seat_ids": seats_bus2})
    assert hold.status_code == 200
    # Booking bus 2 must not flip bus 1 inventory.
    original_inventory = (
        db.query(TripSeat)
        .filter(TripSeat.trip_id == trip.id, TripSeat.status == SeatInventoryStatus.BOOKED)
        .count()
    )
    assert original_inventory == 1
