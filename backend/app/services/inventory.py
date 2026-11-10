from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hold_expiry, utcnow
from app.models import (
    BookingStatus,
    Booking,
    BookingSeat,
    BusSeat,
    SeatHold,
    SeatHoldSeat,
    SeatInventoryStatus,
    Trip,
    TripSeat,
    TripStatus,
)


def lock_trip(db: Session, trip_id: UUID) -> Trip:
    # A single lock order is shared by online checkout, counter sales, expiry,
    # cancellation and bus changes. Refresh identity-map state after waiting.
    trip = db.execute(select(Trip).where(Trip.id == trip_id).with_for_update()
                      .execution_options(populate_existing=True)).scalar_one_or_none()
    if not trip:
        raise NotFoundError("Trip not found")
    return trip


def expire_holds(db: Session, trip_id: UUID | None = None, now: datetime | None = None) -> int:
    now = now or utcnow()
    query = select(SeatHold).where(SeatHold.expires_at <= now, SeatHold.id.in_(
        select(TripSeat.hold_id).where(TripSeat.status == SeatInventoryStatus.HELD)))
    if trip_id:
        query = query.where(SeatHold.trip_id == trip_id)
    holds = db.execute(query.order_by(SeatHold.trip_id, SeatHold.id)).scalars().all()
    released = 0
    for hold in holds:
        lock_trip(db, hold.trip_id)
        seats = db.execute(select(TripSeat).where(TripSeat.hold_id == hold.id)
                           .with_for_update().execution_options(populate_existing=True)).scalars().all()
        for seat in seats:
            if seat.status == SeatInventoryStatus.HELD:
                seat.status = SeatInventoryStatus.AVAILABLE
                seat.hold_id = None
                seat.booking_id = None
                released += 1
        if seats and hold.booking_id:
            booking = db.get(Booking, hold.booking_id)
            if booking and booking.booking_status == BookingStatus.PENDING_PAYMENT:
                booking.booking_status = BookingStatus.EXPIRED
                for item in booking.seats:
                    item.released = True
    db.flush()
    return released


def available_count(db: Session, trip: Trip) -> int:
    expire_holds(db, trip.id)
    return sum(1 for seat in trip.inventory if seat.status == SeatInventoryStatus.AVAILABLE)


def create_hold(db: Session, trip_id: UUID, seat_ids: list[UUID]) -> SeatHold:
    trip = lock_trip(db, trip_id)
    expire_holds(db, trip_id)
    trip = db.execute(
        select(Trip).options(joinedload(Trip.inventory)).where(Trip.id == trip_id)
    ).unique().scalar_one_or_none()
    if not trip or trip.status != TripStatus.PUBLISHED:
        raise NotFoundError("Published trip not found")
    if trip.departure_datetime - timedelta(minutes=trip.booking_cutoff_minutes) <= utcnow():
        raise ConflictError("Booking cutoff has passed")

    unique_ids = list(dict.fromkeys(seat_ids))
    if not unique_ids or len(unique_ids) != len(seat_ids) or len(unique_ids) > 10:
        raise ConflictError("Select between 1 and 10 distinct seats")
    locked = (
        db.execute(
            select(TripSeat)
            .where(TripSeat.trip_id == trip_id, TripSeat.bus_seat_id.in_(unique_ids))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        .scalars()
        .all()
    )
    if len(locked) != len(unique_ids):
        raise NotFoundError("One or more seats do not belong to this trip")
    unavailable = [seat for seat in locked if seat.status != SeatInventoryStatus.AVAILABLE]
    if unavailable:
        raise ConflictError("One or more selected seats are no longer available")

    hold = SeatHold(
        trip_id=trip_id,
        token=secrets.token_urlsafe(24),
        expires_at=hold_expiry(),
        fare_paise=trip.base_fare_paise,
    )
    db.add(hold)
    db.flush()
    for seat in locked:
        seat.status = SeatInventoryStatus.HELD
        seat.hold_id = hold.id
        db.add(SeatHoldSeat(hold_id=hold.id, bus_seat_id=seat.bus_seat_id))
    db.flush()
    return hold


def get_valid_hold(db: Session, token: str) -> SeatHold:
    hold = db.execute(
        select(SeatHold).options(joinedload(SeatHold.seats)).where(SeatHold.token == token)
    ).unique().scalar_one_or_none()
    if not hold:
        raise NotFoundError("Seat hold not found")
    lock_trip(db, hold.trip_id)
    db.refresh(hold)
    expire_holds(db, hold.trip_id)
    if hold.expires_at <= utcnow():
        raise ConflictError("Seat hold has expired")
    if hold.booking_id:
        raise ConflictError("This hold has already been used for a booking")
    return hold


def release_hold_seats(db: Session, hold: SeatHold, to_status: SeatInventoryStatus = SeatInventoryStatus.AVAILABLE) -> None:
    seats = (
        db.execute(select(TripSeat).where(TripSeat.hold_id == hold.id).with_for_update())
        .scalars()
        .all()
    )
    for seat in seats:
        if seat.status == SeatInventoryStatus.HELD:
            seat.status = to_status
            if to_status == SeatInventoryStatus.AVAILABLE:
                seat.hold_id = None
                seat.booking_id = None


def initialize_trip_inventory(db: Session, trip: Trip) -> None:
    seats = db.execute(select(BusSeat).where(BusSeat.bus_id == trip.bus_id, BusSeat.active.is_(True))).scalars().all()
    if not seats:
        raise ConflictError("Configure the bus seat layout before creating a trip")
    for seat in seats:
        db.add(TripSeat(trip_id=trip.id, bus_seat_id=seat.id, status=SeatInventoryStatus.AVAILABLE))
    db.flush()


def block_seats(db: Session, trip_id: UUID, seat_ids: list[UUID], blocked: bool) -> None:
    lock_trip(db, trip_id)
    expire_holds(db, trip_id)
    locked = (
        db.execute(
            select(TripSeat)
            .where(TripSeat.trip_id == trip_id, TripSeat.bus_seat_id.in_(seat_ids))
            .with_for_update()
        )
        .scalars()
        .all()
    )
    if len(locked) != len(set(seat_ids)):
        raise NotFoundError("Seat not found on this trip")
    for seat in locked:
        if blocked:
            if seat.status in {SeatInventoryStatus.BOOKED, SeatInventoryStatus.HELD}:
                raise ConflictError("Cannot block a booked or held seat")
            seat.status = SeatInventoryStatus.BLOCKED
            seat.hold_id = None
        else:
            if seat.status == SeatInventoryStatus.BLOCKED:
                seat.status = SeatInventoryStatus.AVAILABLE
