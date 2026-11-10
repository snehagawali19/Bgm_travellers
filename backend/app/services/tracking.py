from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import TrackingStatus, Trip, TripLiveState, TripLocationPing, TripStatus
from app.services.time_utils import as_utc
from app.services.trips import load_trip

GPS_STALE_SECONDS = 10 * 60
DEFAULT_SIMULATOR_SECONDS = 360
DEFAULT_SPEED_KMH = 62.0

CITY_COORDS: dict[str, tuple[float, float]] = {
    "belgaum": (15.8497, 74.4977),
    "bengaluru": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
}

CORRIDORS: dict[tuple[str, str], list[tuple[float, float, str]]] = {
    ("belgaum", "bengaluru"): [
        (15.8497, 74.4977, "Belgaum Central"),
        (15.4589, 75.0078, "Dharwad"),
        (15.3647, 75.1240, "Hubballi"),
        (14.7951, 75.3991, "Haveri"),
        (14.4644, 75.9218, "Davangere"),
        (14.2251, 76.3980, "Chitradurga"),
        (13.3409, 77.1010, "Tumakuru"),
        (12.9716, 77.5946, "Bengaluru"),
    ],
    ("bengaluru", "mumbai"): [
        (12.9716, 77.5946, "Bengaluru"),
        (13.3409, 77.1010, "Tumakuru"),
        (15.3647, 75.1240, "Hubballi"),
        (16.8524, 74.5815, "Sangli"),
        (18.5204, 73.8567, "Pune"),
        (19.0760, 72.8777, "Mumbai"),
    ],
    ("belgaum", "mumbai"): [
        (15.8497, 74.4977, "Belgaum Central"),
        (16.8524, 74.5815, "Sangli"),
        (16.7050, 74.2433, "Kolhapur"),
        (18.5204, 73.8567, "Pune"),
        (19.0760, 72.8777, "Mumbai"),
    ],
}


@dataclass
class Point:
    lat: float
    lng: float
    name: str = ""


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    inner = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(inner))


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * t


def city_coords(city) -> tuple[float, float]:
    if city.latitude is not None and city.longitude is not None:
        return (city.latitude, city.longitude)
    return CITY_COORDS.get(city.slug, (15.8497, 74.4977))


def route_polyline(trip: Trip) -> list[Point]:
    origin = trip.route.origin_city
    dest = trip.route.destination_city
    key = (origin.slug, dest.slug)
    reverse = (dest.slug, origin.slug)
    if key in CORRIDORS:
        return [Point(lat, lng, name) for lat, lng, name in CORRIDORS[key]]
    if reverse in CORRIDORS:
        return [Point(lat, lng, name) for lat, lng, name in reversed(CORRIDORS[reverse])]
    start, end = city_coords(origin), city_coords(dest)
    points = [Point(start[0], start[1], origin.name)]
    for step in range(1, 6):
        t = step / 6
        points.append(Point(lerp(start[0], end[0], t), lerp(start[1], end[1], t), f"Waypoint {step}"))
    points.append(Point(end[0], end[1], dest.name))
    return points


def _segment_lengths(points: list[Point]) -> list[float]:
    return [
        haversine_km((points[i].lat, points[i].lng), (points[i + 1].lat, points[i + 1].lng))
        for i in range(len(points) - 1)
    ]


def interpolate(points: list[Point], progress: float) -> tuple[Point, float, str]:
    progress = min(1.0, max(0.0, progress))
    lengths = _segment_lengths(points)
    total = sum(lengths) or 1.0
    target = total * progress
    walked = 0.0
    for index, length in enumerate(lengths):
        if walked + length >= target:
            ratio = 0 if length == 0 else (target - walked) / length
            start, end = points[index], points[index + 1]
            heading = bearing_deg((start.lat, start.lng), (end.lat, end.lng))
            landmark = end.name
            return (
                Point(lerp(start.lat, end.lat, ratio), lerp(start.lng, end.lng, ratio), start.name),
                heading,
                landmark,
            )
        walked += length
    last = points[-1]
    prev = points[-2] if len(points) > 1 else last
    return last, bearing_deg((prev.lat, prev.lng), (last.lat, last.lng)), last.name


def schedule_progress(trip: Trip, now=None) -> float:
    now = as_utc(now or utcnow())
    start = as_utc(trip.departure_datetime)
    end = as_utc(trip.estimated_arrival_datetime)
    if now <= start:
        return 0.0
    if now >= end:
        return 1.0
    span = (end - start).total_seconds() or 1
    return (now - start).total_seconds() / span


def status_for_progress(progress: float, trip: Trip, now=None) -> TrackingStatus:
    if trip.status == TripStatus.CANCELLED:
        return TrackingStatus.OFFLINE
    now = as_utc(now or utcnow())
    if progress <= 0 and now < as_utc(trip.departure_datetime):
        minutes_out = (as_utc(trip.departure_datetime) - now).total_seconds() / 60
        return TrackingStatus.BOARDING if minutes_out <= 30 else TrackingStatus.SCHEDULED
    if progress >= 0.97:
        return TrackingStatus.COMPLETED if progress >= 1 else TrackingStatus.ARRIVING
    if progress <= 0.02:
        return TrackingStatus.DEPARTED
    return TrackingStatus.IN_TRANSIT


def _ensure_state(db: Session, trip: Trip) -> TripLiveState:
    state = db.get(TripLiveState, trip.id)
    if state:
        return state
    origin = city_coords(trip.route.origin_city)
    state = TripLiveState(
        trip_id=trip.id,
        latitude=origin[0],
        longitude=origin[1],
        status=TrackingStatus.SCHEDULED,
        source="schedule_estimate",
    )
    db.add(state)
    db.flush()
    return state


def record_ping(
    db: Session,
    trip_id: UUID,
    latitude: float,
    longitude: float,
    heading: float = 0,
    speed_kmh: float = 0,
    source: str = "gps",
    status: TrackingStatus | None = None,
) -> TripLiveState:
    trip = load_trip(db, trip_id)
    if trip.status == TripStatus.CANCELLED:
        raise ConflictError("Cannot track a cancelled trip")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ConflictError("Invalid coordinates")
    ping = TripLocationPing(
        trip_id=trip.id,
        latitude=latitude,
        longitude=longitude,
        heading=heading,
        speed_kmh=speed_kmh,
        source=source,
        recorded_at=utcnow(),
    )
    db.add(ping)
    state = _ensure_state(db, trip)
    points = route_polyline(trip)
    total = sum(_segment_lengths(points)) or 1
    closest = 0.0
    best = 10**9
    walked = 0.0
    for index in range(len(points) - 1):
        start, end = points[index], points[index + 1]
        length = haversine_km((start.lat, start.lng), (end.lat, end.lng))
        for sample in (0.0, 0.5, 1.0):
            lat = lerp(start.lat, end.lat, sample)
            lng = lerp(start.lng, end.lng, sample)
            dist = haversine_km((latitude, longitude), (lat, lng))
            if dist < best:
                best = dist
                closest = (walked + length * sample) / total
        walked += length
    progress = min(1.0, max(0.0, closest))
    _, computed_heading, landmark = interpolate(points, progress)
    remaining_km = total * (1 - progress)
    speed = speed_kmh or DEFAULT_SPEED_KMH
    state.latitude = latitude
    state.longitude = longitude
    state.heading = heading or computed_heading
    state.speed_kmh = speed
    state.progress_percent = round(progress * 100, 2)
    state.source = source
    state.next_landmark = landmark
    state.eta_minutes = int(remaining_km / speed * 60)
    state.last_ping_at = utcnow()
    state.status = status or status_for_progress(progress, trip)
    if source != "simulator":
        state.simulator_active = False
    db.flush()
    return state


def start_simulator(db: Session, trip_id: UUID, duration_seconds: int = DEFAULT_SIMULATOR_SECONDS) -> TripLiveState:
    trip = load_trip(db, trip_id)
    state = _ensure_state(db, trip)
    state.simulator_active = True
    state.simulator_started_at = utcnow()
    state.simulator_duration_seconds = max(60, duration_seconds)
    state.source = "simulator"
    state.status = TrackingStatus.DEPARTED
    db.flush()
    return snapshot(db, trip_id)


def stop_simulator(db: Session, trip_id: UUID) -> TripLiveState:
    trip = load_trip(db, trip_id)
    state = _ensure_state(db, trip)
    state.simulator_active = False
    state.source = "schedule_estimate"
    db.flush()
    return snapshot(db, trip_id)


def snapshot(db: Session, trip_id: UUID) -> dict:
    trip = load_trip(db, trip_id)
    if trip.status not in {TripStatus.PUBLISHED, TripStatus.COMPLETED, TripStatus.CANCELLED}:
        raise NotFoundError("Published trip not found")
    points = route_polyline(trip)
    state = _ensure_state(db, trip)
    now = utcnow()
    gps_fresh = (
        state.source in {"gps", "admin"}
        and (now - as_utc(state.last_ping_at)).total_seconds() <= GPS_STALE_SECONDS
    )
    if state.simulator_active and state.simulator_started_at:
        elapsed = (now - as_utc(state.simulator_started_at)).total_seconds()
        progress = min(1.0, elapsed / max(state.simulator_duration_seconds, 1))
        source = "simulator"
    elif gps_fresh:
        progress = state.progress_percent / 100
        source = state.source
    else:
        progress = schedule_progress(trip, now)
        source = "schedule_estimate"

    point, heading, landmark = interpolate(points, progress)
    total_km = sum(_segment_lengths(points))
    remaining_km = total_km * (1 - progress)
    status = status_for_progress(progress, trip, now)
    speed = DEFAULT_SPEED_KMH if source != "gps" else (state.speed_kmh or DEFAULT_SPEED_KMH)
    if source in {"gps", "admin"} and gps_fresh:
        latitude, longitude, heading = state.latitude, state.longitude, state.heading
    else:
        latitude, longitude = point.lat, point.lng
        state.latitude, state.longitude, state.heading = latitude, longitude, heading
        state.progress_percent = round(progress * 100, 2)
        state.source = source
        state.status = status
        state.next_landmark = landmark
        state.eta_minutes = int(remaining_km / speed * 60) if progress < 1 else 0
        state.last_ping_at = now

    trail = (
        db.execute(
            select(TripLocationPing)
            .where(TripLocationPing.trip_id == trip.id)
            .order_by(TripLocationPing.recorded_at.desc())
            .limit(40)
        )
        .scalars()
        .all()
    )
    trail_points = [{"lat": item.latitude, "lng": item.longitude, "at": item.recorded_at} for item in reversed(trail)]
    if not trail_points:
        sampled = max(2, int(progress * (len(points) - 1)) + 1)
        trail_points = [{"lat": item.lat, "lng": item.lng, "at": None} for item in points[:sampled]]

    origin = points[0]
    dest = points[-1]
    return {
        "trip_id": str(trip.id),
        "route_name": trip.route.route_name,
        "bus_name": trip.bus.display_name,
        "origin_name": trip.route.origin_city.name,
        "destination_name": trip.route.destination_city.name,
        "departure_datetime": trip.departure_datetime,
        "estimated_arrival_datetime": trip.estimated_arrival_datetime,
        "status": status.value,
        "source": source,
        "source_label": {
            "gps": "Live GPS",
            "admin": "Operator update",
            "simulator": "Demo replay",
            "schedule_estimate": "Schedule estimate until a GPS device is connected",
        }.get(source, source),
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "heading": round(heading, 1),
        "speed_kmh": round(speed, 1),
        "progress_percent": round(progress * 100, 1),
        "next_landmark": landmark,
        "eta_minutes": 0 if progress >= 1 else max(0, int(remaining_km / speed * 60)),
        "distance_km": round(total_km, 1),
        "remaining_km": round(remaining_km, 1),
        "polyline": [{"lat": item.lat, "lng": item.lng, "name": item.name} for item in points],
        "origin": {"lat": origin.lat, "lng": origin.lng, "name": origin.name},
        "destination": {"lat": dest.lat, "lng": dest.lng, "name": dest.name},
        "trail": trail_points,
        "last_updated_at": now,
        "simulator_active": state.simulator_active,
    }


def list_trackable(db: Session) -> list[dict]:
    trips = (
        db.execute(
            select(Trip)
            .where(Trip.status.in_([TripStatus.PUBLISHED, TripStatus.COMPLETED]))
            .order_by(Trip.departure_datetime.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    cards = []
    for trip in trips:
        loaded = load_trip(db, trip.id)
        data = snapshot(db, loaded.id)
        cards.append(
            {
                "trip_id": data["trip_id"],
                "route_name": data["route_name"],
                "bus_name": data["bus_name"],
                "origin_name": data["origin_name"],
                "destination_name": data["destination_name"],
                "departure_datetime": data["departure_datetime"],
                "status": data["status"],
                "progress_percent": data["progress_percent"],
                "next_landmark": data["next_landmark"],
                "source_label": data["source_label"],
            }
        )
    return cards
