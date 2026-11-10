from __future__ import annotations

import io
import secrets
import string
from uuid import UUID

import qrcode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hmac_sign
from app.models import Booking


def generate_public_reference() -> str:
    return secrets.token_hex(8).upper()


def generate_access_token() -> str:
    return secrets.token_urlsafe(24)


def generate_pnr(db: Session) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        candidate = "BGM" + "".join(secrets.choice(alphabet) for _ in range(6))
        exists = db.execute(select(Booking.id).where(Booking.pnr == candidate)).scalar_one_or_none()
        if not exists:
            return candidate
    raise RuntimeError("Unable to allocate a unique PNR")


def verification_payload(booking: Booking) -> str:
    return hmac_sign(f"{booking.public_reference}:{booking.pnr}:{booking.id}")


def qr_png_base64(payload: str) -> bytes:
    image = qrcode.make(payload)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
