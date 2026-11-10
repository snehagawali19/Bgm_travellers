import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_customer_optional
from app.config import get_settings
from app.core.errors import PaymentError
from app.database import get_db
from app.limiter import limiter
from app.models import City, CustomerUser, Route, SeatInventoryStatus, TripStatus
from app.schemas import (
    BookingCreateIn,
    CancelIn,
    CityOut,
    HoldIn,
    LookupIn,
    PaymentVerifyIn,
    RouteOut,
    SeatMapSeat,
    StopOut,
    TripSeatMapOut,
)
from app.services.booking import (
    assert_booking_access,
    create_booking,
    expire_pending_bookings,
    load_booking,
    lookup_booking,
    process_webhook,
    serialize_booking,
    verify_checkout_payment,
)
from app.services.cancellations import estimate_refund, request_cancellation
from app.services.inventory import create_hold, expire_holds
from app.services.payments import get_payment_provider
from app.services.trips import load_trip, search_trips, to_trip_card
from app.services.tracking import list_trackable, snapshot as tracking_snapshot

router = APIRouter()


def _city_out(city: City) -> CityOut:
    return CityOut(
        id=city.id,
        name=city.name,
        slug=city.slug,
        state=city.state,
        country=city.country,
        latitude=city.latitude,
        longitude=city.longitude,
        active=city.active,
        aliases=[alias.alias for alias in city.aliases],
    )


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(select(1))
    settings = get_settings()
    return {
        "status": "ok",
        "payments_live_enabled": settings.payments_live_enabled,
        "payment_provider": settings.payment_provider,
    }


@router.get("/cities", response_model=list[CityOut])
def list_cities(bookable: bool = True, db: Session = Depends(get_db)) -> list[CityOut]:
    query = select(City).options(selectinload(City.aliases)).where(City.active.is_(True))
    cities = db.execute(query).scalars().all()
    if not bookable:
        return [_city_out(city) for city in cities]
    bookable_ids = {
        row[0]
        for row in db.execute(
            select(Route.origin_city_id).where(Route.active.is_(True))
        ).all()
    } | {
        row[0]
        for row in db.execute(
            select(Route.destination_city_id).where(Route.active.is_(True))
        ).all()
    }
    return [_city_out(city) for city in cities if city.id in bookable_ids]


@router.get("/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db)) -> list[RouteOut]:
    routes = (
        db.execute(
            select(Route)
            .options(selectinload(Route.stops), selectinload(Route.origin_city), selectinload(Route.destination_city))
            .where(Route.active.is_(True))
        )
        .scalars()
        .all()
    )
    return [
        RouteOut(
            id=route.id,
            origin_city_id=route.origin_city_id,
            destination_city_id=route.destination_city_id,
            origin_name=route.origin_city.name,
            destination_name=route.destination_city.name,
            route_name=route.route_name,
            estimated_duration_minutes=route.estimated_duration_minutes,
            active=route.active,
            stops=[StopOut.model_validate(stop) for stop in route.stops if stop.active],
        )
        for route in routes
    ]


@router.get("/trips/search")
def trip_search(
    origin_city_id: UUID,
    destination_city_id: UUID,
    travel_date: date,
    passengers: int = Query(ge=1, le=10, default=1),
    db: Session = Depends(get_db),
):
    expire_pending_bookings(db)
    trips = search_trips(db, origin_city_id, destination_city_id, travel_date.isoformat(), passengers)
    db.commit()
    return [to_trip_card(db, trip) for trip in trips]


@router.get("/trips/{trip_id}", response_model=TripSeatMapOut)
def trip_detail(trip_id: UUID, db: Session = Depends(get_db)) -> TripSeatMapOut:
    expire_holds(db, trip_id)
    trip = load_trip(db, trip_id)
    if trip.status != TripStatus.PUBLISHED:
        from app.core.errors import NotFoundError

        raise NotFoundError("Published trip not found")
    inventory = {item.bus_seat_id: item.status for item in trip.inventory}
    seats = [
        SeatMapSeat(
            id=seat.id,
            seat_number=seat.seat_number,
            seat_type=seat.seat_type.value if hasattr(seat.seat_type, "value") else seat.seat_type,
            row_no=seat.row_no,
            col_no=seat.col_no,
            deck=seat.deck,
            status=inventory.get(seat.id, SeatInventoryStatus.AVAILABLE).value
            if hasattr(inventory.get(seat.id, SeatInventoryStatus.AVAILABLE), "value")
            else str(inventory.get(seat.id, "available")),
        )
        for seat in sorted([item.bus_seat for item in trip.inventory], key=lambda item: (item.row_no, item.col_no))
    ]
    policy = trip.cancellation_policy
    db.commit()
    return TripSeatMapOut(
        trip=to_trip_card(db, trip),
        seats=seats,
        hold_ttl_minutes=get_settings().hold_ttl_minutes,
        cancellation_disclaimer=policy.disclaimer if policy else None,
    )


@router.post("/holds")
@limiter.limit("30/minute")
def hold_seats(request: Request, payload: HoldIn, db: Session = Depends(get_db)):
    hold = create_hold(db, payload.trip_id, payload.seat_ids)
    trip = load_trip(db, payload.trip_id)
    wanted = {str(seat_id) for seat_id in payload.seat_ids}
    numbers = [item.bus_seat.seat_number for item in trip.inventory if str(item.bus_seat_id) in wanted]
    db.commit()
    return {
        "hold_token": hold.token,
        "trip_id": str(hold.trip_id),
        "seat_numbers": numbers,
        "expires_at": hold.expires_at,
        "fare_paise": hold.fare_paise * len(payload.seat_ids),
    }


@router.post("/bookings")
@limiter.limit("20/minute")
def create_customer_booking(
    request: Request,
    payload: BookingCreateIn,
    db: Session = Depends(get_db),
    customer: CustomerUser | None = Depends(get_current_customer_optional),
):
    booking = create_booking(db, payload, customer_user_id=customer.id if customer else None)
    db.commit()
    return serialize_booking(db, load_booking(db, booking.id), include_secrets=True)


@router.post("/payments/verify")
@limiter.limit("30/minute")
def verify_payment(request: Request, payload: PaymentVerifyIn, db: Session = Depends(get_db)):
    booking = verify_checkout_payment(
        db,
        payload.public_reference,
        payload.gateway_order_id,
        payload.gateway_payment_id,
        payload.gateway_signature,
    )
    db.commit()
    return serialize_booking(db, booking, include_secrets=True)


@router.post("/payments/webhook")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
    x_razorpay_event_id: str | None = Header(default=None),
):
    raw = await request.body()
    signature = x_razorpay_signature or x_webhook_signature or ""
    provider = get_payment_provider()
    if not provider.verify_webhook(raw, signature):
        raise PaymentError("Invalid webhook signature", status_code=400)
    payload = json.loads(raw.decode() or "{}")
    event_id = str(x_razorpay_event_id or payload.get("id") or payload.get("event_id") or "")
    event_type = str(payload.get("event") or payload.get("event_type") or "")
    if not event_id:
        raise PaymentError("Webhook event id missing")
    process_webhook(db, provider.name, event_id, event_type, payload)
    db.commit()
    return {"received": True}


@router.post("/bookings/lookup")
@limiter.limit("10/minute")
def booking_lookup(request: Request, payload: LookupIn, db: Session = Depends(get_db)):
    booking = lookup_booking(db, payload.pnr, payload.phone)
    db.commit()
    return serialize_booking(db, booking, include_secrets=True)


@router.get("/bookings/{public_reference}")
def get_booking(
    public_reference: str,
    access_token: str | None = None,
    db: Session = Depends(get_db),
):
    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    return serialize_booking(db, booking, include_secrets=bool(access_token))


@router.get("/bookings/{public_reference}/refund-estimate")
def refund_estimate(public_reference: str, access_token: str, db: Session = Depends(get_db)):
    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    booking.trip = load_trip(db, booking.trip_id)
    return estimate_refund(booking)


@router.post("/bookings/{public_reference}/cancel")
def cancel_booking(
    public_reference: str,
    payload: CancelIn,
    access_token: str,
    db: Session = Depends(get_db),
):
    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    booking.trip = load_trip(db, booking.trip_id)
    request_cancellation(db, booking, "customer", payload.reason)
    db.commit()
    return serialize_booking(db, load_booking(db, booking.id), include_secrets=True)


@router.get("/bookings/{public_reference}/ticket.png")
def ticket_qr(public_reference: str, access_token: str, db: Session = Depends(get_db)):
    from app.services.tickets import qr_png_base64

    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    if not booking.verification_code or booking.booking_status.value not in {"confirmed", "exception"}:
        from app.core.errors import ConflictError

        raise ConflictError("Ticket is not available until payment is confirmed")
    return Response(content=qr_png_base64(booking.verification_code), media_type="image/png")


@router.post("/bookings/{public_reference}/retry-payment")
def retry_payment(public_reference: str, access_token: str, db: Session = Depends(get_db)):
    from app.services.inventory import lock_trip
    from app.models import BookingStatus
    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    lock_trip(db, booking.trip_id)
    expire_holds(db, booking.trip_id)
    if booking.booking_status != BookingStatus.PENDING_PAYMENT:
        from app.core.errors import ConflictError
        raise ConflictError("Payment cannot be retried; the hold expired or booking is already paid")
    db.commit()
    # Reuse the gateway order and quoted fare; do not create a second charge intent.
    return serialize_booking(db, booking, include_secrets=True)


@router.get("/notifications/whatsapp/webhook")
def whatsapp_challenge(request: Request):
    import hmac
    settings = get_settings()
    token = request.query_params.get("hub.verify_token", "")
    if not settings.whatsapp_verify_token or not hmac.compare_digest(token, settings.whatsapp_verify_token):
        from app.core.errors import ForbiddenError
        raise ForbiddenError("Invalid verification token")
    return Response(content=request.query_params.get("hub.challenge", ""), media_type="text/plain")


@router.post("/notifications/whatsapp/webhook")
async def whatsapp_delivery(request: Request, db: Session = Depends(get_db)):
    import hashlib
    import hmac
    from app.services.notifications import record_delivery
    raw = await request.body()
    secret = get_settings().whatsapp_app_secret
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
        from app.core.errors import ForbiddenError
        raise ForbiddenError("Invalid webhook signature")
    record_delivery(db, json.loads(raw))
    db.commit()
    return {"received": True}


@router.get("/tracking/trips")
def trackable_trips(db: Session = Depends(get_db)):
    data = list_trackable(db)
    db.commit()
    return data


@router.get("/trips/{trip_id}/tracking")
def trip_tracking(trip_id: UUID, db: Session = Depends(get_db)):
    data = tracking_snapshot(db, trip_id)
    db.commit()
    return data


@router.get("/bookings/{public_reference}/tracking")
def booking_tracking(public_reference: str, access_token: str | None = None, db: Session = Depends(get_db)):
    booking = load_booking(db, public_reference=public_reference)
    assert_booking_access(booking, access_token)
    data = tracking_snapshot(db, booking.trip_id)
    db.commit()
    return data
