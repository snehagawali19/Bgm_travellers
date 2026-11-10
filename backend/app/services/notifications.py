"""Durable WhatsApp outbox. Provider acceptance and delivery are separate states."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.core.security import utcnow
from app.models import Notification


def enqueue(db, booking, kind, message, suffix=""):
    settings = get_settings()
    trip = booking.trip
    seats = ", ".join(s.bus_seat.seat_number for s in booking.seats if not s.released)
    pickup = booking.pickup_snapshot or {}
    boarding = " / ".join(str(pickup.get(k) or "") for k in ("stop_name", "address", "landmark"))
    ticket = f"{settings.public_app_url}/bookings/{booking.public_reference}?access_token={booking.access_token}"
    body = (f"{message} Reference: {booking.pnr or booking.public_reference}. {trip.route.route_name}. "
            f"Departure: {trip.departure_datetime.astimezone(ZoneInfo('Asia/Kolkata')):%d %b %Y %H:%M} IST. "
            f"Seats: {seats or 'see ticket'}. Boarding: {boarding}. Ticket: {ticket}")
    db.execute(insert(Notification).values(booking_id=booking.id, kind=kind, recipient="91" + booking.customer_phone[-10:],
        event_key=f"{booking.id}:{kind}:{suffix}", message=body).on_conflict_do_nothing(index_elements=["event_key"]))


def send_whatsapp(item):
    s = get_settings()
    if not s.whatsapp_access_token or not s.whatsapp_phone_number_id:
        raise RuntimeError("WhatsApp credentials are not configured")
    payload = {"messaging_product": "whatsapp", "to": item.recipient, "type": "template",
        "template": {"name": s.whatsapp_template_name, "language": {"code": s.whatsapp_template_language},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": item.message}]}]},
        "biz_opaque_callback_data": str(item.id)}
    response = httpx.post(f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_number_id}/messages",
                         headers={"Authorization": f"Bearer {s.whatsapp_access_token}"}, json=payload, timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(f"WhatsApp rejected delivery (HTTP {response.status_code})")
    return response.json()["messages"][0]["id"]


def deliver_one(db):
    s = get_settings()
    item = db.execute(select(Notification).where(Notification.status.in_(["pending", "retry"]),
        Notification.next_attempt_at <= utcnow(), Notification.attempts < s.notification_max_attempts)
        .order_by(Notification.next_attempt_at).with_for_update(skip_locked=True).limit(1)).scalar_one_or_none()
    if not item:
        return False
    item.attempts += 1
    try:
        item.provider_message_id = send_whatsapp(item)
        item.status = "accepted"
        item.last_error = None
    except Exception as exc:
        item.status = "failed" if item.attempts >= s.notification_max_attempts else "retry"
        item.last_error = str(exc)[:255] if isinstance(exc, RuntimeError) else "Delivery request failed; retry scheduled"
        item.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 30 * 2 ** item.attempts))
    return True


def record_delivery(db, payload):
    from uuid import UUID
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status in change.get("value", {}).get("statuses", []):
                query = select(Notification).where(Notification.provider_message_id == status.get("id"))
                item = db.execute(query.with_for_update()).scalar_one_or_none()
                if not item and status.get("biz_opaque_callback_data"):
                    try:
                        item = db.get(Notification, UUID(status["biz_opaque_callback_data"]))
                    except ValueError:
                        continue
                if not item:
                    continue
                state = status.get("status")
                ranks = {"pending": 0, "retry": 0, "failed": 0, "accepted": 1, "sent": 2, "delivered": 3, "read": 4}
                if state in {"sent", "delivered", "read"} and ranks[state] > ranks.get(item.status, 0):
                    item.status = state
                    item.last_error = None
                elif state == "failed" and item.status not in {"delivered", "read"}:
                    item.status = "retry" if item.attempts < get_settings().notification_max_attempts else "failed"
                    item.last_error = "WhatsApp reported delivery failure"
                    item.next_attempt_at = utcnow() + timedelta(minutes=5)
