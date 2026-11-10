from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.security import clear_admin_cookies, new_csrf_token, set_admin_cookies, utcnow, verify_password
from app.database import get_db
from app.models import (
    AdminUser,
    AuditLog,
    Booking,
    Bus,
    BusSeat,
    BusStatus,
    BusType,
    City,
    CityAlias,
    PaymentOrder,
    Refund,
    Route,
    RouteStop,
    SeatType,
    TrackingStatus,
    Trip,
    TripStatus,
)
from app.schemas import (
    AdminLoginIn,
    AdminUserOut,
    BlockSeatsIn,
    BusIn,
    CityIn,
    RouteIn,
    SeatLayoutIn,
    SimulatorIn,
    StopIn,
    TrackingPingIn,
    TripIn,
)
from app.api.deps import get_current_admin
from app.services.booking import load_booking, serialize_booking
from app.services.cancellations import admin_retry_refund, cancel_trip_and_bookings
from app.services.inventory import block_seats
from app.services.trips import assert_bus_available, confirmed_bookings_for_trip, create_trip, load_trip, to_trip_card
from app.services.tracking import list_trackable, record_ping, snapshot as tracking_snapshot, start_simulator, stop_simulator

router = APIRouter(prefix="/admin")


def audit(db: Session, admin: AdminUser, action: str, entity_type: str, entity_id: str, details: dict | None = None) -> None:
    db.add(
        AuditLog(
            admin_user_id=admin.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


@router.post("/auth/login")
def login(payload: AdminLoginIn, response: Response, db: Session = Depends(get_db)):
    admin = db.execute(select(AdminUser).where(AdminUser.email == str(payload.email).lower())).scalar_one_or_none()
    if not admin or not admin.active or not verify_password(payload.password, admin.password_hash):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid credentials")
    csrf = new_csrf_token()
    set_admin_cookies(response, admin.id, csrf)
    return {"admin": AdminUserOut(id=admin.id, email=admin.email, name=admin.name, role=admin.role), "csrf_token": csrf}


@router.post("/auth/logout")
def logout(response: Response, admin: AdminUser = Depends(get_current_admin)):
    clear_admin_cookies(response)
    return {"ok": True}


@router.get("/auth/me")
def me(admin: AdminUser = Depends(get_current_admin)):
    return AdminUserOut(id=admin.id, email=admin.email, name=admin.name, role=admin.role)


@router.get("/cities")
def admin_cities(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    cities = db.execute(select(City).options(selectinload(City.aliases))).scalars().all()
    return [
        {
            "id": str(city.id),
            "name": city.name,
            "slug": city.slug,
            "state": city.state,
            "country": city.country,
            "latitude": city.latitude,
            "longitude": city.longitude,
            "active": city.active,
            "aliases": [alias.alias for alias in city.aliases],
        }
        for city in cities
    ]


@router.post("/cities")
def create_city(payload: CityIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    city = City(
        name=payload.name,
        slug=payload.slug,
        state=payload.state,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        active=payload.active,
    )
    db.add(city)
    db.flush()
    for alias in payload.aliases:
        db.add(CityAlias(city_id=city.id, alias=alias))
    audit(db, admin, "create_city", "city", str(city.id), {"name": city.name})
    db.commit()
    return {"id": str(city.id)}


@router.patch("/cities/{city_id}")
def update_city(city_id: UUID, payload: CityIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    city = db.get(City, city_id)
    if not city:
        raise NotFoundError("City not found")
    city.name = payload.name
    city.slug = payload.slug
    city.state = payload.state
    city.country = payload.country
    city.latitude = payload.latitude
    city.longitude = payload.longitude
    city.active = payload.active
    audit(db, admin, "update_city", "city", str(city.id))
    db.commit()
    return {"ok": True}


@router.get("/buses")
def admin_buses(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    buses = db.execute(select(Bus).options(selectinload(Bus.seats))).scalars().all()
    return [
        {
            "id": str(bus.id),
            "registration_number": bus.registration_number,
            "display_name": bus.display_name,
            "bus_type": bus.bus_type.value,
            "seat_capacity": bus.seat_capacity,
            "status": bus.status.value,
            "amenities": bus.amenities,
            "seats": [
                {
                    "id": str(seat.id),
                    "seat_number": seat.seat_number,
                    "seat_type": seat.seat_type.value,
                    "row_no": seat.row_no,
                    "col_no": seat.col_no,
                    "deck": seat.deck,
                    "active": seat.active,
                }
                for seat in sorted(bus.seats, key=lambda item: (item.row_no, item.col_no))
                if seat.active
            ],
        }
        for bus in buses
    ]


@router.post("/buses")
def create_bus(payload: BusIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    bus = Bus(
        registration_number=payload.registration_number,
        display_name=payload.display_name,
        bus_type=BusType(payload.bus_type),
        seat_capacity=payload.seat_capacity,
        status=BusStatus(payload.status),
        amenities=payload.amenities,
    )
    db.add(bus)
    db.flush()
    audit(db, admin, "create_bus", "bus", str(bus.id), {"registration_number": payload.registration_number})
    db.commit()
    db.refresh(bus)
    return {"id": str(bus.id)}


@router.patch("/buses/{bus_id}")
def update_bus(bus_id: UUID, payload: BusIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    bus = db.execute(select(Bus).where(Bus.id == bus_id).with_for_update()).scalar_one_or_none()
    if not bus:
        raise NotFoundError("Bus not found")
    if payload.status != "active":
        future = db.execute(
            select(Trip).where(
                Trip.bus_id == bus.id,
                Trip.status.in_([TripStatus.PUBLISHED, TripStatus.CLOSED, TripStatus.DRAFT]),
                Trip.estimated_arrival_datetime >= utcnow(),
            )
        ).scalars().all()
        if future:
            raise ConflictError("Deactivate blocked: this bus has published future trips. Cancel or reassign them first.")
    bus.registration_number = payload.registration_number
    bus.display_name = payload.display_name
    bus.bus_type = BusType(payload.bus_type)
    bus.seat_capacity = payload.seat_capacity
    bus.status = BusStatus(payload.status)
    bus.amenities = payload.amenities
    audit(db, admin, "update_bus", "bus", str(bus.id))
    db.commit()
    return {"ok": True}


@router.put("/buses/{bus_id}/seats")
def replace_seats(
    bus_id: UUID,
    payload: list[SeatLayoutIn],
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    from app.services.operations import replace_layout
    bus = replace_layout(db, bus_id, payload)
    audit(db, admin, "replace_seats", "bus", str(bus.id), {"count": len(payload)})
    db.commit()
    return {"ok": True, "seat_capacity": bus.seat_capacity}


@router.get("/routes")
def admin_routes(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    routes = db.execute(
        select(Route).options(
            selectinload(Route.stops),
            selectinload(Route.origin_city),
            selectinload(Route.destination_city),
        )
    ).scalars().all()
    return [
        {
            "id": str(route.id),
            "origin_city_id": str(route.origin_city_id),
            "destination_city_id": str(route.destination_city_id),
            "origin_name": route.origin_city.name,
            "destination_name": route.destination_city.name,
            "route_name": route.route_name,
            "estimated_duration_minutes": route.estimated_duration_minutes,
            "active": route.active,
            "stops": route.stops,
        }
        for route in routes
    ]


@router.post("/routes")
def create_route(payload: RouteIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if payload.origin_city_id == payload.destination_city_id:
        raise ConflictError("Origin and destination must be different")
    route = Route(
        origin_city_id=payload.origin_city_id,
        destination_city_id=payload.destination_city_id,
        route_name=payload.route_name,
        estimated_duration_minutes=payload.estimated_duration_minutes,
        active=payload.active,
    )
    db.add(route)
    db.flush()
    audit(db, admin, "create_route", "route", str(route.id))
    db.commit()
    return {"id": str(route.id)}


@router.patch("/routes/{route_id}")
def update_route(route_id: UUID, payload: RouteIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    route = db.get(Route, route_id)
    if not route:
        raise NotFoundError("Route not found")
    if payload.origin_city_id == payload.destination_city_id:
        raise ConflictError("Origin and destination must be different")
    if (payload.origin_city_id, payload.destination_city_id) != (route.origin_city_id, route.destination_city_id) and db.execute(select(Trip.id).where(Trip.route_id == route.id)).first():
        raise ConflictError("Create a new directional route; existing trip directions cannot change")
    if not payload.active:
        future = db.execute(
            select(Trip).where(
                Trip.route_id == route.id,
                Trip.status.in_([TripStatus.PUBLISHED, TripStatus.CLOSED, TripStatus.DRAFT]),
                Trip.departure_datetime >= utcnow(),
            )
        ).scalars().all()
        if future:
            raise ConflictError("Deactivate blocked: this route has published future trips. Cancel them first.")
    route.origin_city_id = payload.origin_city_id
    route.destination_city_id = payload.destination_city_id
    route.route_name = payload.route_name
    route.estimated_duration_minutes = payload.estimated_duration_minutes
    route.active = payload.active
    audit(db, admin, "update_route", "route", str(route.id))
    db.commit()
    return {"ok": True}


@router.post("/routes/{route_id}/stops")
def add_stop(route_id: UUID, payload: StopIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    route = db.get(Route, route_id)
    if not route:
        raise NotFoundError("Route not found")
    stop = RouteStop(route_id=route.id, **payload.model_dump())
    db.add(stop)
    audit(db, admin, "add_stop", "route", str(route.id), {"stop": payload.stop_name})
    db.commit()
    db.refresh(stop)
    return {"id": str(stop.id)}


@router.get("/trips")
def admin_trips(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    trips = db.execute(select(Trip).order_by(Trip.departure_datetime.desc())).scalars().all()
    return [to_trip_card(db, load_trip(db, trip.id)) for trip in trips]


@router.post("/trips")
def admin_create_trip(payload: TripIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    trip = create_trip(
        db,
        route_id=payload.route_id,
        bus_id=payload.bus_id,
        departure_datetime=payload.departure_datetime,
        estimated_arrival_datetime=payload.estimated_arrival_datetime,
        base_fare_paise=payload.base_fare_paise,
        booking_cutoff_minutes=payload.booking_cutoff_minutes,
        cancellation_policy_id=payload.cancellation_policy_id,
        status=TripStatus(payload.status),
        published_at=utcnow() if payload.status == "published" else None,
    )
    audit(db, admin, "create_trip", "trip", str(trip.id))
    db.commit()
    return {"id": str(trip.id)}


@router.post("/trips/{trip_id}/publish")
def publish_trip(trip_id: UUID, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from app.services.inventory import lock_trip
    lock_trip(db, trip_id)
    trip = load_trip(db, trip_id)
    if trip.status not in {TripStatus.DRAFT, TripStatus.CLOSED} or trip.departure_datetime <= utcnow():
        raise ConflictError("Only future draft or closed trips can be published")
    assert_bus_available(db, trip.bus_id, trip.departure_datetime, trip.estimated_arrival_datetime, trip.id)
    trip.status = TripStatus.PUBLISHED
    trip.published_at = utcnow()
    audit(db, admin, "publish_trip", "trip", str(trip.id))
    db.commit()
    return {"ok": True}


@router.post("/trips/{trip_id}/cancel")
def admin_cancel_trip(trip_id: UUID, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    trip = load_trip(db, trip_id)
    affected = cancel_trip_and_bookings(db, trip)
    audit(db, admin, "cancel_trip", "trip", str(trip.id), {"bookings": len(affected)})
    db.commit()
    return {"ok": True, "affected_bookings": len(affected)}


@router.post("/trips/{trip_id}/block-seats")
def admin_block_seats(
    trip_id: UUID,
    payload: BlockSeatsIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    block_seats(db, trip_id, payload.seat_ids, payload.blocked)
    audit(db, admin, "block_seats", "trip", str(trip_id), payload.model_dump(mode="json"))
    db.commit()
    return {"ok": True}


@router.get("/trips/{trip_id}/manifest")
def trip_manifest(trip_id: UUID, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    import csv
    import io
    trip = load_trip(db, trip_id)
    bookings = confirmed_bookings_for_trip(db, trip.id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["pnr", "passenger_name", "age", "gender", "seat", "phone", "email", "pickup", "drop", "checked_in"])
    def safe(value):
        value = str(value)
        return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
    for booking in bookings:
        full = load_booking(db, booking.id)
        for seat in full.seats:
            if seat.released:
                continue
            writer.writerow(map(safe, [
                        full.pnr or "",
                        seat.passenger_name,
                        str(seat.passenger_age),
                        seat.passenger_gender,
                        seat.bus_seat.seat_number,
                        full.customer_phone,
                        full.customer_email,
                        full.pickup_stop.stop_name if full.pickup_stop else "",
                        full.dropoff_stop.stop_name if full.dropoff_stop else "",
                        seat.checked_in_at.isoformat() if seat.checked_in_at else "",
                    ]))
    filename = f"manifest-{trip.id}.csv"
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/bookings")
def admin_bookings(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    bookings = db.execute(select(Booking).order_by(Booking.created_at.desc())).scalars().all()
    return [serialize_booking(db, load_booking(db, item.id), include_secrets=False) for item in bookings]


@router.get("/payments")
def admin_payments(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    orders = db.execute(select(PaymentOrder).order_by(PaymentOrder.created_at.desc())).scalars().all()
    return [
        {
            "id": str(order.id),
            "booking_id": str(order.booking_id),
            "booking_reference": order.booking.public_reference,
            "channel": order.booking.channel,
            "gateway_order_id": order.gateway_order_id,
            "amount_paise": order.amount_paise,
            "status": order.status.value,
            "created_at": order.created_at,
            "transactions": [
                {
                    "gateway_payment_id": txn.gateway_payment_id,
                    "status": txn.status.value,
                    "amount_paise": txn.amount_paise,
                    "method": txn.method,
                }
                for txn in order.transactions
            ],
        }
        for order in orders
    ]


@router.get("/refunds")
def admin_refunds(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    refunds = db.execute(select(Refund).order_by(Refund.created_at.desc())).scalars().all()
    return [
        {
            "id": str(item.id),
            "cancellation_request_id": str(item.cancellation_request_id),
            "channel": item.cancellation.booking.channel,
            "booking_reference": item.cancellation.booking.public_reference,
            "amount_paise": item.amount_paise,
            "gateway_refund_id": item.gateway_refund_id,
            "status": item.status.value,
            "created_at": item.created_at,
        }
        for item in refunds
    ]


@router.post("/refunds/{refund_id}/retry")
def retry_refund(refund_id: UUID, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    refund = admin_retry_refund(db, refund_id)
    audit(db, admin, "retry_refund", "refund", str(refund.id))
    db.commit()
    return {"ok": True, "status": refund.status.value}


@router.get("/tracking")
def admin_tracking(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return list_trackable(db)


@router.get("/trips/{trip_id}/tracking")
def admin_trip_tracking(trip_id: UUID, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    data = tracking_snapshot(db, trip_id)
    db.commit()
    return data


@router.post("/trips/{trip_id}/tracking/ping")
def admin_tracking_ping(
    trip_id: UUID,
    payload: TrackingPingIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    status = TrackingStatus(payload.status) if payload.status else None
    record_ping(
        db,
        trip_id,
        payload.latitude,
        payload.longitude,
        payload.heading,
        payload.speed_kmh,
        source="admin",
        status=status,
    )
    audit(db, admin, "tracking_ping", "trip", str(trip_id), {"lat": payload.latitude, "lng": payload.longitude})
    data = tracking_snapshot(db, trip_id)
    db.commit()
    return data


@router.post("/trips/{trip_id}/tracking/simulate")
def admin_tracking_simulate(
    trip_id: UUID,
    payload: SimulatorIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if payload.action == "start":
        start_simulator(db, trip_id, payload.duration_seconds)
        audit(db, admin, "tracking_simulate_start", "trip", str(trip_id))
    else:
        stop_simulator(db, trip_id)
        audit(db, admin, "tracking_simulate_stop", "trip", str(trip_id))
    data = tracking_snapshot(db, trip_id)
    db.commit()
    return data
