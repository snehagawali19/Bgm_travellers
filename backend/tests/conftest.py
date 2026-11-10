from __future__ import annotations

import os
from collections.abc import Generator
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("PAYMENT_PROVIDER", "fake")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://bgm:bgm_dev_password@localhost:5433/bgm_travels_test",
)
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("ADMIN_EMAIL", "admin@bgmtravels.in")
os.environ.setdefault("ADMIN_PASSWORD", "ChangeMe_Admin123!")

from app.config import get_settings

get_settings.cache_clear()

from app.database import Base, get_db
from app.main import app
from app.models import (
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
from app.core.security import hash_password, utcnow
from app.models import AdminUser
from app.seed import seater_layout
from app.services.inventory import initialize_trip_inventory

IST = ZoneInfo("Asia/Kolkata")
TEST_URL = os.environ["TEST_DATABASE_URL"]


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_URL, future=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    SessionTesting = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionTesting()
    yield session
    session.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_admin(db: Session) -> AdminUser:
    admin = AdminUser(
        email="admin@bgmtravels.in",
        password_hash=hash_password("ChangeMe_Admin123!"),
        name="Test Admin",
        role="operator",
        active=True,
    )
    db.add(admin)
    db.flush()
    return admin


def add_city(db: Session, name: str, slug: str, aliases: list[str] | None = None) -> City:
    from app.services.tracking import CITY_COORDS

    lat, lng = CITY_COORDS.get(slug, (None, None))
    city = City(
        name=name,
        slug=slug,
        state="Karnataka" if slug != "mumbai" else "Maharashtra",
        country="India",
        latitude=lat,
        longitude=lng,
    )
    db.add(city)
    db.flush()
    for alias in aliases or []:
        db.add(CityAlias(city_id=city.id, alias=alias))
    return city


def add_bus(db: Session, registration: str, name: str, rows: int = 10) -> Bus:
    layout = seater_layout(rows)
    bus = Bus(
        registration_number=registration,
        display_name=name,
        bus_type=BusType.SEATER,
        seat_capacity=len(layout),
        status=BusStatus.ACTIVE,
        amenities=["ac"],
    )
    db.add(bus)
    db.flush()
    for seat in layout:
        db.add(BusSeat(bus_id=bus.id, **seat))
    db.flush()
    return bus


def add_route(db: Session, origin: City, dest: City) -> Route:
    route = Route(
        origin_city_id=origin.id,
        destination_city_id=dest.id,
        route_name=f"{origin.name} → {dest.name}",
        estimated_duration_minutes=510,
        active=True,
    )
    db.add(route)
    db.flush()
    db.add_all(
        [
            RouteStop(
                route_id=route.id,
                city_id=origin.id,
                stop_name=f"{origin.name} Pickup",
                pickup_allowed=True,
                dropoff_allowed=False,
                display_order=1,
            ),
            RouteStop(
                route_id=route.id,
                city_id=dest.id,
                stop_name=f"{dest.name} Drop",
                pickup_allowed=False,
                dropoff_allowed=True,
                display_order=2,
            ),
        ]
    )
    db.flush()
    return route


def add_policy(db: Session) -> CancellationPolicy:
    policy = CancellationPolicy(
        name="sample",
        version="sample-v1",
        rules={"rules": [{"min_hours_before_departure": 0, "refund_percent": 100}]},
        disclaimer="SAMPLE POLICY",
        active=True,
    )
    db.add(policy)
    db.flush()
    return policy


def add_trip(db: Session, route: Route, bus: Bus, hours_ahead: int = 48, fare: int = 89900) -> Trip:
    policy_obj = db.execute(select(CancellationPolicy)).scalars().first() or add_policy(db)
    departure = utcnow() + timedelta(hours=hours_ahead)
    trip = Trip(
        route_id=route.id,
        bus_id=bus.id,
        departure_datetime=departure,
        estimated_arrival_datetime=departure + timedelta(minutes=510),
        base_fare_paise=fare,
        status=TripStatus.PUBLISHED,
        published_at=utcnow(),
        cancellation_policy_id=policy_obj.id if policy_obj else None,
    )
    db.add(trip)
    db.flush()
    initialize_trip_inventory(db, trip)
    return trip


def seed_launch(db: Session) -> dict:
    add_admin(db)
    belgaum = add_city(db, "Belgaum", "belgaum", ["Belagavi"])
    bengaluru = add_city(db, "Bengaluru", "bengaluru", ["Bangalore"])
    bus = add_bus(db, "KA-22-N-2201", "BGM Comfort 01")
    outbound = add_route(db, belgaum, bengaluru)
    inbound = add_route(db, bengaluru, belgaum)
    t1 = add_trip(db, outbound, bus, hours_ahead=48)
    t2 = add_trip(db, inbound, bus, hours_ahead=80)
    db.flush()
    return {
        "belgaum": belgaum,
        "bengaluru": bengaluru,
        "bus": bus,
        "outbound": outbound,
        "inbound": inbound,
        "trip_out": t1,
        "trip_in": t2,
    }


def seat_ids(bus: Bus, count: int = 1) -> list[str]:
    return [str(seat.id) for seat in sorted(bus.seats, key=lambda s: s.seat_number)[:count]]
