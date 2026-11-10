from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import get_settings
from app.core.security import utcnow
from app.core.errors import ConflictError, NotFoundError
from app.models import (
    Booking,
    BookingStatus,
    Bus,
    BusStatus,
    City,
    Route,
    RouteStop,
    Trip,
    TripStatus,
)
from app.schemas import StopOut, TripCardOut
from app.services.inventory import available_count, initialize_trip_inventory
from app.services.time_utils import as_utc, ist_day_bounds


def trips_overlap(a_start, a_end, b_start, b_end, turnaround) -> bool:
    a_start, a_end, b_start, b_end = map(as_utc, (a_start, a_end, b_start, b_end))
    buffer = timedelta(minutes=turnaround)
    return not (a_end + buffer <= b_start or b_end + buffer <= a_start)


def assert_bus_available(db: Session, bus_id: UUID, departure, arrival, ignore_trip_id: UUID | None = None) -> None:
    bus = db.execute(select(Bus).where(Bus.id == bus_id).with_for_update()).scalar_one_or_none()
    if not bus:
        raise NotFoundError("Bus not found")
    if bus.status != BusStatus.ACTIVE:
        raise ConflictError("Bus is not active")
    turnaround = get_settings().bus_turnaround_minutes
    query = select(Trip).where(
        Trip.bus_id == bus_id,
        Trip.status.in_([TripStatus.DRAFT, TripStatus.PUBLISHED, TripStatus.CLOSED]),
    )
    if ignore_trip_id:
        query = query.where(Trip.id != ignore_trip_id)
    existing = db.execute(query).scalars().all()
    for trip in existing:
        if trips_overlap(departure, arrival, trip.departure_datetime, trip.estimated_arrival_datetime, turnaround):
            raise ConflictError("Bus is already assigned to an overlapping trip")


def search_trips(db: Session, origin_id: UUID, destination_id: UUID, travel_date: str, passengers: int) -> list[Trip]:
    start, end = ist_day_bounds(travel_date)
    route = db.execute(
        select(Route).where(
            Route.origin_city_id == origin_id,
            Route.destination_city_id == destination_id,
            Route.active.is_(True),
        )
    ).scalar_one_or_none()
    if not route:
        return []
    trips = (
        db.execute(
            select(Trip)
            .options(
                joinedload(Trip.route).joinedload(Route.origin_city),
                joinedload(Trip.route).joinedload(Route.destination_city),
                joinedload(Trip.route).selectinload(Route.stops),
                joinedload(Trip.bus),
                selectinload(Trip.inventory),
                joinedload(Trip.cancellation_policy),
            )
            .where(
                Trip.route_id == route.id,
                Trip.status == TripStatus.PUBLISHED,
                Trip.departure_datetime >= start,
                Trip.departure_datetime <= end,
            )
            .order_by(Trip.departure_datetime)
        )
        .unique()
        .scalars()
        .all()
    )
    return [trip for trip in trips if trip.departure_datetime - timedelta(minutes=trip.booking_cutoff_minutes) > utcnow()
            and available_count(db, trip) >= passengers]


def load_trip(db: Session, trip_id: UUID) -> Trip:
    trip = (
        db.execute(
            select(Trip)
            .options(
                joinedload(Trip.route).joinedload(Route.origin_city),
                joinedload(Trip.route).joinedload(Route.destination_city),
                joinedload(Trip.route).selectinload(Route.stops),
                joinedload(Trip.bus).selectinload(Bus.seats),
                selectinload(Trip.inventory),
                joinedload(Trip.cancellation_policy),
            )
            .where(Trip.id == trip_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if not trip:
        raise NotFoundError("Trip not found")
    return trip


def to_trip_card(db: Session, trip: Trip) -> TripCardOut:
    pickups = [
        StopOut.model_validate(stop).model_copy(update={"stop_datetime": trip.departure_datetime + timedelta(minutes=stop.offset_minutes)})
        for stop in sorted(trip.route.stops, key=lambda s: s.display_order)
        if stop.active and stop.pickup_allowed
    ]
    drops = [
        StopOut.model_validate(stop).model_copy(update={"stop_datetime": trip.departure_datetime + timedelta(minutes=stop.offset_minutes)})
        for stop in sorted(trip.route.stops, key=lambda s: s.display_order)
        if stop.active and stop.dropoff_allowed
    ]
    return TripCardOut(
        id=trip.id,
        route_id=trip.route_id,
        route_name=trip.route.route_name,
        origin_name=trip.route.origin_city.name,
        destination_name=trip.route.destination_city.name,
        departure_datetime=trip.departure_datetime,
        estimated_arrival_datetime=trip.estimated_arrival_datetime,
        duration_minutes=int((trip.estimated_arrival_datetime - trip.departure_datetime).total_seconds() / 60),
        base_fare_paise=trip.base_fare_paise,
        bus_id=trip.bus_id,
        bus_name=trip.bus.display_name,
        bus_type=trip.bus.bus_type.value,
        amenities=trip.bus.amenities or [],
        available_seats=available_count(db, trip),
        total_seats=len(trip.inventory),
        pickup_stops=pickups,
        dropoff_stops=drops,
        status=trip.status.value,
        booking_cutoff_minutes=trip.booking_cutoff_minutes,
    )


def create_trip(db: Session, **kwargs) -> Trip:
    if as_utc(kwargs["estimated_arrival_datetime"]) <= as_utc(kwargs["departure_datetime"]):
        raise ConflictError("Arrival must be after departure, including overnight journeys")
    route = db.get(Route, kwargs["route_id"])
    if not route or not route.active:
        raise ConflictError("Select an active route")
    from app.models import CancellationPolicy
    policy_id = kwargs.get("cancellation_policy_id")
    policy = db.get(CancellationPolicy, policy_id) if policy_id else db.execute(
        select(CancellationPolicy).where(CancellationPolicy.active.is_(True)).order_by(CancellationPolicy.created_at.desc())
    ).scalars().first()
    if policy_id and (not policy or not policy.active):
        raise ConflictError("Select an active cancellation policy")
    kwargs["cancellation_policy_id"] = policy.id if policy else None
    assert_bus_available(db, kwargs["bus_id"], kwargs["departure_datetime"], kwargs["estimated_arrival_datetime"])
    trip = Trip(**kwargs)
    db.add(trip)
    db.flush()
    initialize_trip_inventory(db, trip)
    if trip.status == TripStatus.PUBLISHED:
        trip.published_at = trip.published_at or trip.created_at
    return trip


def city_has_bookable_route(db: Session, city_id: UUID) -> bool:
    return (
        db.execute(
            select(Route.id).where(
                Route.active.is_(True),
                or_(Route.origin_city_id == city_id, Route.destination_city_id == city_id),
            )
        ).first()
        is not None
    )


def confirmed_bookings_for_trip(db: Session, trip_id: UUID) -> list[Booking]:
    return (
        db.execute(
            select(Booking).where(
                Booking.trip_id == trip_id,
                Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.EXCEPTION]),
                Booking.pnr.is_not(None),
            )
        )
        .scalars()
        .all()
    )
