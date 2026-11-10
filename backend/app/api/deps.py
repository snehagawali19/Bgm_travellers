from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import (
    ADMIN_COOKIE,
    CUSTOMER_COOKIE,
    read_admin_session_token,
    read_customer_session_token,
    require_csrf,
)
from app.database import get_db
from app.models import AdminUser, CustomerUser


def db_session(db: Session = Depends(get_db)) -> Session:
    return db


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    require_csrf(request)
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    admin_id: UUID = read_admin_session_token(token)
    admin = db.get(AdminUser, admin_id)
    if not admin or not admin.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # Legacy operator accounts are owners; new accounts use explicit roles.
    if admin.role not in {"owner", "operator", "booking_staff"}:
        raise HTTPException(status_code=403, detail="Unknown staff role")
    if admin.role == "booking_staff":
        path = request.url.path.removeprefix("/api/v1/admin")
        readable = path in {"/auth/me", "/trips", "/bookings", "/routes", "/buses", "/tracking"}
        readable = readable or (path.startswith("/trips/") and path.endswith(("/manifest", "/passengers", "/inventory", "/tracking")))
        writable = path in {"/auth/logout", "/counter-bookings"} or (path.startswith("/booking-seats/") and path.endswith("/check-in"))
        if not (readable if request.method in {"GET", "HEAD"} else writable):
            raise HTTPException(status_code=403, detail="Owner permission required")
    return admin


def get_current_admin_optional(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    return get_current_admin(request, db)


def get_current_customer(request: Request, db: Session = Depends(get_db)) -> CustomerUser:
    require_csrf(request)
    customer = get_current_customer_optional(request, db)
    if not customer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return customer


def get_current_customer_optional(request: Request, db: Session = Depends(get_db)) -> CustomerUser | None:
    token = request.cookies.get(CUSTOMER_COOKIE)
    if not token:
        return None
    try:
        customer_id: UUID = read_customer_session_token(token)
    except HTTPException:
        return None
    customer = db.get(CustomerUser, customer_id)
    if not customer or not customer.active:
        return None
    return customer
