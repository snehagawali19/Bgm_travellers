from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin import audit
from app.api.deps import get_current_admin
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password, utcnow
from app.database import get_db
from app.models import (AdminUser, AuditLog, Booking, BookingSeat, BookingStatus, CancellationPolicy,
    Notification, PaymentTransaction, PaymentTransactionStatus, RecurringSchedule, Refund, RefundStatus,
    RouteStop, SeatLayout, Trip, TripSeat, TripStatus)
from app.schemas import (CounterBookingIn, GenerateTripsIn, LayoutTemplateIn, PolicyIn, ScheduleIn,
    SeatLayoutIn, StaffIn, StopIn, SwapBusIn, TripIn)
from app.services.booking import load_booking, serialize_booking, reconcile_booking
from app.services.inventory import lock_trip, expire_holds
from app.services.operations import counter_booking, generate_trips, replace_layout, swap_bus
from app.services.trips import load_trip, assert_bus_available
from app.services.notifications import enqueue

router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_admin)])


def require(db, model, key):
    row = db.get(model, key)
    if row is None:
        raise NotFoundError("Record not found")
    return row


@router.get("/layouts")
def layouts(db: Session = Depends(get_db)):
    return db.execute(select(SeatLayout).order_by(SeatLayout.name)).scalars().all()


@router.post("/layouts")
def save_layout(payload: LayoutTemplateIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    row = SeatLayout(name=payload.name, seats=[s.model_dump() for s in payload.seats])
    db.add(row)
    db.flush()
    audit(db, admin, "create_layout", "layout", str(row.id))
    db.commit()
    return row


@router.post("/buses/{bus_id}/layouts/{layout_id}")
def apply_layout(bus_id: UUID, layout_id: UUID, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    layout = require(db, SeatLayout, layout_id)
    replace_layout(db, bus_id, [SeatLayoutIn.model_validate(s) for s in layout.seats])
    audit(db, admin, "apply_layout", "bus", str(bus_id), {"layout_id": str(layout_id)})
    db.commit()
    return {"ok": True}


@router.patch("/routes/{route_id}/stops/{stop_id}")
def update_stop(route_id: UUID, stop_id: UUID, payload: StopIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    stop = require(db, RouteStop, stop_id)
    if stop.route_id != route_id:
        raise NotFoundError("Stop is not on this route")
    for key, value in payload.model_dump().items():
        setattr(stop, key, value)
    audit(db, admin, "update_stop", "stop", str(stop.id))
    db.commit()
    return {"ok": True}


@router.get("/schedules")
def schedules(db: Session = Depends(get_db)):
    return db.execute(select(RecurringSchedule)).scalars().all()


@router.post("/schedules")
def add_schedule(payload: ScheduleIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    row = RecurringSchedule(name=payload.name, active=payload.active, definition=payload.model_dump(mode="json"))
    db.add(row)
    db.flush()
    audit(db, admin, "create_schedule", "schedule", str(row.id))
    db.commit()
    return row


@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: UUID, payload: ScheduleIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    row = db.execute(select(RecurringSchedule).where(RecurringSchedule.id == schedule_id).with_for_update()).scalar_one_or_none()
    if not row:
        raise NotFoundError("Schedule not found")
    row.name, row.active, row.definition = payload.name, payload.active, payload.model_dump(mode="json")
    audit(db, admin, "update_schedule", "schedule", str(row.id))
    db.commit()
    return row


@router.post("/schedules/{schedule_id}/generate")
def generate(schedule_id: UUID, payload: GenerateTripsIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    ids = generate_trips(db, schedule_id, payload)
    audit(db, admin, "generate_trips", "schedule", str(schedule_id), {"trip_ids": ids})
    db.commit()
    return {"created": len(ids), "trip_ids": ids}


@router.post("/trips/{trip_id}/close")
def close_trip(trip_id: UUID, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    trip = lock_trip(db, trip_id)
    if trip.status != TripStatus.PUBLISHED:
        raise ConflictError("Only published trips can be closed")
    trip.status = TripStatus.CLOSED
    audit(db, admin, "close_trip", "trip", str(trip.id))
    db.commit()
    return {"ok": True}


@router.patch("/trips/{trip_id}")
def edit_trip(trip_id: UUID, payload: TripIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    trip = lock_trip(db, trip_id)
    if trip.status in {TripStatus.CANCELLED, TripStatus.COMPLETED}:
        raise ConflictError("Cannot edit a cancelled or completed trip")
    if payload.route_id != trip.route_id or payload.bus_id != trip.bus_id:
        raise ConflictError("Route cannot change. Use the bus replacement workflow to change buses")
    if payload.estimated_arrival_datetime <= payload.departure_datetime:
        raise ConflictError("Arrival must be after departure")
    assert_bus_available(db, trip.bus_id, payload.departure_datetime, payload.estimated_arrival_datetime, trip.id)
    changed = trip.departure_datetime != payload.departure_datetime
    for field in ("departure_datetime", "estimated_arrival_datetime", "base_fare_paise", "booking_cutoff_minutes"):
        setattr(trip, field, getattr(payload, field))
    if payload.cancellation_policy_id:
        require(db, CancellationPolicy, payload.cancellation_policy_id)
        trip.cancellation_policy_id = payload.cancellation_policy_id
    if changed:
        for booking in db.execute(select(Booking).where(Booking.trip_id == trip.id, Booking.pnr.is_not(None))).scalars():
            for field in ("pickup_snapshot", "dropoff_snapshot"):
                snapshot = getattr(booking, field)
                if snapshot:
                    setattr(booking, field, {**snapshot, "stop_datetime": (trip.departure_datetime + timedelta(minutes=snapshot.get("offset_minutes", 0))).isoformat()})
            enqueue(db, booking, "trip_changed", "Your departure time changed. Please review your updated ticket.", suffix=uuid4().hex)
    audit(db, admin, "edit_trip", "trip", str(trip.id), payload.model_dump(mode="json"))
    db.commit()
    return {"ok": True}


@router.post("/trips/{trip_id}/swap-bus")
def replacement(trip_id: UUID, payload: SwapBusIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    swap_bus(db, trip_id, payload)
    audit(db, admin, "swap_bus", "trip", str(trip_id), payload.model_dump(mode="json"))
    db.commit()
    return {"ok": True}


@router.get("/trips/{trip_id}/inventory")
def inventory(trip_id: UUID, db: Session = Depends(get_db)):
    expire_holds(db, trip_id)
    trip = load_trip(db, trip_id)
    rows = [{"id": str(s.bus_seat_id), "seat_number": s.bus_seat.seat_number, "status": s.status.value,
             "seat_type": s.bus_seat.seat_type.value, "row_no": s.bus_seat.row_no, "col_no": s.bus_seat.col_no, "deck": s.bus_seat.deck} for s in trip.inventory]
    db.commit()
    return rows


@router.post("/counter-bookings")
def counter(payload: CounterBookingIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    booking = counter_booking(db, payload)
    audit(db, admin, "counter_booking", "booking", str(booking.id), {"channel": payload.channel, "method": payload.payment_method})
    db.commit()
    return serialize_booking(db, load_booking(db, booking.id), include_secrets=True)


@router.get("/trips/{trip_id}/passengers")
def passengers(trip_id: UUID, db: Session = Depends(get_db)):
    require(db, Trip, trip_id)
    bookings = db.execute(select(Booking).where(Booking.trip_id == trip_id, Booking.pnr.is_not(None),
        Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.EXCEPTION]))).scalars().all()
    return [serialize_booking(db, load_booking(db, b.id)) for b in bookings]


class CheckInIn(BaseModel):
    checked_in: bool = True


@router.post("/booking-seats/{seat_id}/check-in")
def check_in(seat_id: UUID, payload: CheckInIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    seat = require(db, BookingSeat, seat_id)
    trip = lock_trip(db, seat.trip_id)
    db.refresh(seat)
    if seat.released or seat.booking.booking_status not in {BookingStatus.CONFIRMED, BookingStatus.EXCEPTION} or trip.status == TripStatus.CANCELLED:
        raise ConflictError("Only active confirmed passengers can check in")
    seat.checked_in_at = (seat.checked_in_at or utcnow()) if payload.checked_in else None
    audit(db, admin, "check_in" if payload.checked_in else "undo_check_in", "booking_seat", str(seat.id))
    db.commit()
    return {"checked_in_at": seat.checked_in_at}


@router.post("/bookings/{reference}/reconcile")
def reconcile(reference: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    booking = reconcile_booking(db, load_booking(db, public_reference=reference))
    audit(db, admin, "reconcile_payment", "booking", str(booking.id))
    db.commit()
    return serialize_booking(db, booking)


class OfflineRefundIn(BaseModel):
    reference: str = Field(min_length=3, max_length=120)


@router.post("/refunds/{refund_id}/record-offline")
def offline_refund(refund_id: UUID, payload: OfflineRefundIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    from app.services.cancellations import apply_refund_result
    refund = require(db, Refund, refund_id)
    lock_trip(db, refund.cancellation.booking.trip_id)
    db.refresh(refund)
    if refund.cancellation.booking.channel == "online":
        raise ConflictError("Online refunds must go through the gateway")
    if refund.status != RefundStatus.PROCESSED:
        apply_refund_result(db, refund, {"id": "offline_" + str(refund.id), "status": "processed"})
        audit(db, admin, "record_offline_refund", "refund", str(refund.id), {"reference": payload.reference})
    db.commit()
    return {"ok": True}


@router.get("/reports")
def reports(db: Session = Depends(get_db)):
    expire_holds(db)
    trips = []
    for trip in db.execute(select(Trip).order_by(Trip.departure_datetime.desc())).scalars():
        counts = {state: sum(s.status.value == state for s in trip.inventory) for state in ("available", "held", "booked", "blocked")}
        trips.append({"id": str(trip.id), "route_name": trip.route.route_name, "departure_datetime": trip.departure_datetime,
            "total": len(trip.inventory), **counts, "occupancy_percent": round(counts["booked"] * 100 / max(1, len(trip.inventory)), 1)})
    collections = {"online": 0, "counter": 0, "phone": 0}
    for txn in db.execute(select(PaymentTransaction).where(PaymentTransaction.status.in_([
            PaymentTransactionStatus.CAPTURED, PaymentTransactionStatus.REFUNDED]))).scalars():
        collections[txn.order.booking.channel] += txn.amount_paise
    refunds = db.execute(select(Refund)).scalars().all()
    result = {"trips": trips, "gross_collections_paise": collections,
        "refunded_paise": sum(r.amount_paise for r in refunds if r.status == RefundStatus.PROCESSED),
        "pending_refunds_paise": sum(r.amount_paise for r in refunds if r.status != RefundStatus.PROCESSED),
        "pending_refunds_count": sum(r.status != RefundStatus.PROCESSED for r in refunds)}
    db.commit()
    return result


@router.get("/audit")
def audit_log(db: Session = Depends(get_db)):
    return db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).scalars().all()


@router.get("/staff")
def staff(db: Session = Depends(get_db)):
    return [{"id": str(u.id), "name": u.name, "email": u.email, "role": u.role, "active": u.active}
            for u in db.execute(select(AdminUser)).scalars()]


@router.post("/staff")
def add_staff(payload: StaffIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    if db.execute(select(AdminUser.id).where(AdminUser.email == str(payload.email).lower())).first():
        raise ConflictError("Staff email already exists")
    user = AdminUser(email=str(payload.email).lower(), name=payload.name, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    audit(db, admin, "create_staff", "admin", str(user.id), {"role": user.role})
    db.commit()
    return {"id": str(user.id)}


@router.post("/staff/{staff_id}/deactivate")
def deactivate_staff(staff_id: UUID, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    user = require(db, AdminUser, staff_id)
    if user.id == admin.id or user.role in {"owner", "operator"}:
        raise ConflictError("Only another booking staff account can be deactivated here")
    user.active = False
    audit(db, admin, "deactivate_staff", "admin", str(user.id))
    db.commit()
    return {"ok": True}


@router.get("/policies")
def policies(db: Session = Depends(get_db)):
    return db.execute(select(CancellationPolicy)).scalars().all()


@router.post("/policies")
def add_policy(payload: PolicyIn, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    row = CancellationPolicy(name=payload.name, version=payload.version, disclaimer=payload.disclaimer,
        rules={"cutoff_minutes": payload.cutoff_minutes, "rules": [r.model_dump() for r in payload.rules]})
    db.add(row)
    db.flush()
    audit(db, admin, "create_policy", "policy", str(row.id))
    db.commit()
    return row


@router.get("/notifications")
def notifications(db: Session = Depends(get_db)):
    # Ticket access tokens in message bodies are deliberately excluded from this list.
    return [{"id": str(n.id), "booking_id": str(n.booking_id), "kind": n.kind, "recipient": n.recipient,
             "status": n.status, "attempts": n.attempts, "last_error": n.last_error, "created_at": n.created_at}
            for n in db.execute(select(Notification).order_by(Notification.created_at.desc()).limit(500)).scalars()]


@router.post("/notifications/{notification_id}/retry")
def retry_notification(notification_id: UUID, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    n = db.execute(select(Notification).where(Notification.id == notification_id).with_for_update()).scalar_one_or_none()
    if not n:
        raise NotFoundError("Notification not found")
    if n.status not in {"failed", "retry"}:
        raise ConflictError("Only failed deliveries can be retried")
    n.status, n.attempts, n.next_attempt_at = "pending", 0, utcnow()
    audit(db, admin, "retry_notification", "notification", str(n.id))
    db.commit()
    return {"ok": True}
