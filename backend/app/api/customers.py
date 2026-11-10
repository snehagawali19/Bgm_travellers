from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_customer
from app.core.security import (
    clear_customer_cookies,
    hash_password,
    new_csrf_token,
    set_customer_cookies,
    verify_password,
)
from app.database import get_db
from app.limiter import limiter
from app.models import Booking, CustomerUser
from app.schemas import CustomerLoginIn, CustomerOut, CustomerRegisterIn
from app.services.booking import load_booking, serialize_booking

router = APIRouter(prefix="/auth")


def _out(user: CustomerUser) -> CustomerOut:
    return CustomerOut(id=user.id, email=user.email, phone=user.phone, name=user.name)


@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, payload: CustomerRegisterIn, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    existing = db.execute(
        select(CustomerUser).where(or_(CustomerUser.email == email, CustomerUser.phone == payload.phone))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account already exists with this email or mobile number")
    user = CustomerUser(
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    csrf = new_csrf_token()
    set_customer_cookies(response, user.id, csrf)
    return {"customer": _out(user), "csrf_token": csrf}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, payload: CustomerLoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.execute(select(CustomerUser).where(CustomerUser.email == str(payload.email).lower())).scalar_one_or_none()
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    csrf = new_csrf_token()
    set_customer_cookies(response, user.id, csrf)
    return {"customer": _out(user), "csrf_token": csrf}


@router.post("/logout")
def logout(response: Response, customer: CustomerUser = Depends(get_current_customer)):
    clear_customer_cookies(response)
    return {"ok": True}


@router.get("/me")
def me(customer: CustomerUser = Depends(get_current_customer)):
    return _out(customer)


@router.get("/bookings")
def my_bookings(db: Session = Depends(get_db), customer: CustomerUser = Depends(get_current_customer)):
    bookings = db.execute(
        select(Booking).where(Booking.customer_user_id == customer.id).order_by(Booking.created_at.desc())
    ).scalars().all()
    return [serialize_booking(db, load_booking(db, booking.id), include_secrets=True) for booking in bookings]
