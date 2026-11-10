from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    AdminUser,
    CustomerUser,
    Bus,
    BusSeat,
    BusStatus,
    BusType,
    CancellationPolicy,
    City,
    CityAlias,
    Route,
    RouteStop,
    SeatType,
    Trip,
    TripStatus,
)
from app.services.inventory import initialize_trip_inventory
from app.services.tracking import CITY_COORDS
from app.services.trips import assert_bus_available

IST = ZoneInfo("Asia/Kolkata")
SAMPLE_POLICY = {
    "rules": [
        {"min_hours_before_departure": 24, "refund_percent": 100},
        {"min_hours_before_departure": 6, "refund_percent": 50},
        {"min_hours_before_departure": 0, "refund_percent": 0},
    ]
}
DISCLAIMER = "SAMPLE POLICY FOR DEVELOPMENT — not the operator's final commercial terms."


def seater_layout(rows: int = 10) -> list[dict]:
    columns = [("A", 1, SeatType.WINDOW), ("B", 2, SeatType.AISLE), ("C", 3, SeatType.AISLE), ("D", 4, SeatType.WINDOW)]
    layout = []
    for row in range(1, rows + 1):
        for letter, col, seat_type in columns:
            layout.append(
                {
                    "seat_number": f"{row}{letter}",
                    "seat_type": seat_type,
                    "row_no": row,
                    "col_no": col,
                    "deck": "lower",
                }
            )
    return layout


def get_or_create_city(db, name: str, slug: str, state: str, aliases: list[str]) -> City:
    city = db.execute(select(City).where(City.slug == slug)).scalar_one_or_none()
    lat, lng = CITY_COORDS.get(slug, (None, None))
    if city:
        if city.latitude is None and lat is not None:
            city.latitude, city.longitude = lat, lng
        return city
    city = City(name=name, slug=slug, state=state, country="India", latitude=lat, longitude=lng, active=True)
    db.add(city)
    db.flush()
    for alias in aliases:
        db.add(CityAlias(city_id=city.id, alias=alias))
    return city


def seed(days: int = 10) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        admin = db.execute(select(AdminUser).where(AdminUser.email == settings.admin_email.lower())).scalar_one_or_none()
        if not admin:
            db.add(
                AdminUser(
                    email=settings.admin_email.lower(),
                    password_hash=hash_password(settings.admin_password),
                    name=settings.admin_name,
                    role="owner",
                    active=True,
                )
            )

        customer = db.execute(select(CustomerUser).where(CustomerUser.email == "user@bgmtravels.in")).scalar_one_or_none()
        if not customer:
            db.add(
                CustomerUser(
                    email="user@bgmtravels.in",
                    phone="9876543210",
                    password_hash=hash_password("User123"),
                    name="Demo Traveller",
                    active=True,
                )
            )

        belgaum = get_or_create_city(db, "Belgaum", "belgaum", "Karnataka", ["Belagavi", "Belgaum"])
        bengaluru = get_or_create_city(db, "Bengaluru", "bengaluru", "Karnataka", ["Bangalore", "Bengaluru"])

        policy = db.execute(select(CancellationPolicy).where(CancellationPolicy.version == "sample-v1")).scalar_one_or_none()
        if not policy:
            policy = CancellationPolicy(
                name="Sample windowed refund",
                version="sample-v1",
                rules=SAMPLE_POLICY,
                disclaimer=DISCLAIMER,
                active=True,
            )
            db.add(policy)
            db.flush()

        bus = db.execute(select(Bus).where(Bus.registration_number == "KA-22-N-2201")).scalar_one_or_none()
        if not bus:
            bus = Bus(
                registration_number="KA-22-N-2201",
                display_name="BGM Comfort 01",
                bus_type=BusType.SEATER,
                seat_capacity=40,
                status=BusStatus.ACTIVE,
                amenities=["ac", "charging_point", "water_bottle", "reading_light"],
            )
            db.add(bus)
            db.flush()
            for seat in seater_layout():
                db.add(BusSeat(bus_id=bus.id, **seat))

        def ensure_route(origin: City, dest: City, minutes: int) -> Route:
            route = db.execute(
                select(Route).where(Route.origin_city_id == origin.id, Route.destination_city_id == dest.id)
            ).scalar_one_or_none()
            if route:
                return route
            route = Route(
                origin_city_id=origin.id,
                destination_city_id=dest.id,
                route_name=f"{origin.name} → {dest.name}",
                estimated_duration_minutes=minutes,
                active=True,
            )
            db.add(route)
            db.flush()
            db.add_all(
                [
                    RouteStop(
                        route_id=route.id,
                        city_id=origin.id,
                        stop_name=f"{origin.name} Central Bus Stand",
                        address=f"{origin.name}, Karnataka",
                        pickup_allowed=True,
                        dropoff_allowed=False,
                        display_order=1,
                    ),
                    RouteStop(
                        route_id=route.id,
                        city_id=origin.id,
                        stop_name=f"{origin.name} Bypass Pickup",
                        address=f"{origin.name} bypass",
                        pickup_allowed=True,
                        dropoff_allowed=False,
                        display_order=2,
                        offset_minutes=30,
                    ),
                    RouteStop(
                        route_id=route.id,
                        city_id=dest.id,
                        stop_name=f"{dest.name} Central Bus Stand",
                        address=f"{dest.name}, Karnataka",
                        pickup_allowed=False,
                        dropoff_allowed=True,
                        display_order=3,
                        offset_minutes=480,
                    ),
                    RouteStop(
                        route_id=route.id,
                        city_id=dest.id,
                        stop_name=f"{dest.name} City Drop",
                        address=f"{dest.name} city",
                        pickup_allowed=False,
                        dropoff_allowed=True,
                        display_order=4,
                        offset_minutes=510,
                    ),
                ]
            )
            return route

        outbound = ensure_route(belgaum, bengaluru, 510)
        inbound = ensure_route(bengaluru, belgaum, 510)

        today = datetime.now(IST).date()
        for offset in range(days):
            day = today + timedelta(days=offset)
            pairs = [
                (outbound, datetime(day.year, day.month, day.day, 21, 30, tzinfo=IST)),
                (inbound, datetime(day.year, day.month, day.day, 21, 30, tzinfo=IST)),
            ]
            # One physical bus cannot run both directions the same night.
            route, departure = pairs[offset % 2]
            arrival = departure + timedelta(minutes=route.estimated_duration_minutes)
            exists = db.execute(
                select(Trip).where(Trip.route_id == route.id, Trip.departure_datetime == departure)
            ).scalar_one_or_none()
            if exists:
                continue
            try:
                assert_bus_available(db, bus.id, departure, arrival)
            except Exception:
                continue
            trip = Trip(
                route_id=route.id,
                bus_id=bus.id,
                departure_datetime=departure,
                estimated_arrival_datetime=arrival,
                base_fare_paise=89900,
                status=TripStatus.PUBLISHED,
                published_at=datetime.now(IST),
                cancellation_policy_id=policy.id,
            )
            db.add(trip)
            db.flush()
            initialize_trip_inventory(db, trip)

        db.commit()
        print("Seed complete: Belgaum ↔ Bengaluru, one bus, published trips, sample cancellation policy.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
