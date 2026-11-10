from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BusStatus(str, enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class BusType(str, enum.Enum):
    SEATER = "seater"
    SLEEPER = "sleeper"
    SEMI_SLEEPER = "semi_sleeper"


class SeatType(str, enum.Enum):
    WINDOW = "window"
    AISLE = "aisle"
    SINGLE = "single"


class TripStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class SeatInventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"
    BLOCKED = "blocked"


class BookingStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    EXCEPTION = "exception"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class PaymentOrderStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentTransactionStatus(str, enum.Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class CancellationStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RefundStatus(str, enum.Enum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class TrackingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    IN_TRANSIT = "in_transit"
    ARRIVING = "arriving"
    COMPLETED = "completed"
    OFFLINE = "offline"


def utcnow() -> datetime:
    from app.core.security import utcnow as _utcnow

    return _utcnow()


class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="India")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    aliases: Mapped[list[CityAlias]] = relationship(back_populates="city", cascade="all, delete-orphan")


class CityAlias(Base):
    __tablename__ = "city_aliases"
    __table_args__ = (UniqueConstraint("alias", name="uq_city_alias"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)

    city: Mapped[City] = relationship(back_populates="aliases")


class Bus(Base):
    __tablename__ = "buses"
    __table_args__ = (UniqueConstraint("registration_number", name="uq_bus_registration"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_number: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bus_type: Mapped[BusType] = mapped_column(Enum(BusType, name="bus_type"), default=BusType.SEATER)
    seat_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BusStatus] = mapped_column(Enum(BusStatus, name="bus_status"), default=BusStatus.ACTIVE)
    amenities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    seats: Mapped[list[BusSeat]] = relationship(back_populates="bus", cascade="all, delete-orphan")
    trips: Mapped[list[Trip]] = relationship(back_populates="bus")


class BusSeat(Base):
    __tablename__ = "bus_seats"
    __table_args__ = (Index("uq_active_bus_seat_number", "bus_id", "seat_number", unique=True,
                           postgresql_where=text("active IS TRUE")),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buses.id"), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    seat_type: Mapped[SeatType] = mapped_column(Enum(SeatType, name="seat_type"), default=SeatType.AISLE)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    col_no: Mapped[int] = mapped_column(Integer, nullable=False)
    deck: Mapped[str] = mapped_column(String(20), default="lower")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bus: Mapped[Bus] = relationship(back_populates="seats")


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (
        Index(
            "uq_route_origin_dest_active",
            "origin_city_id",
            "destination_city_id",
            unique=True,
            postgresql_where=text("active IS TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin_city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    destination_city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    route_name: Mapped[str] = mapped_column(String(160), nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    origin_city: Mapped[City] = relationship(foreign_keys=[origin_city_id])
    destination_city: Mapped[City] = relationship(foreign_keys=[destination_city_id])
    stops: Mapped[list[RouteStop]] = relationship(back_populates="route", cascade="all, delete-orphan")
    trips: Mapped[list[Trip]] = relationship(back_populates="route")


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id"), nullable=False)
    city_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cities.id"))
    stop_name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(255), default="")
    landmark: Mapped[str] = mapped_column(String(255), default="", server_default="")
    offset_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pickup_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    dropoff_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    route: Mapped[Route] = relationship(back_populates="stops")
    city: Mapped[City | None] = relationship()


class CancellationPolicy(Base):
    __tablename__ = "cancellation_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (Index("ix_trips_route_departure", "route_id", "departure_datetime"),
                     UniqueConstraint("schedule_id", "service_date", name="uq_schedule_date"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id"), nullable=False)
    bus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buses.id"), nullable=False)
    departure_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_arrival_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    base_fare_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_cutoff_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurring_schedules.id"))
    service_date: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[TripStatus] = mapped_column(Enum(TripStatus, name="trip_status"), default=TripStatus.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cancellation_policies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    route: Mapped[Route] = relationship(back_populates="trips")
    bus: Mapped[Bus] = relationship(back_populates="trips")
    cancellation_policy: Mapped[CancellationPolicy | None] = relationship()
    inventory: Mapped[list[TripSeat]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    bookings: Mapped[list[Booking]] = relationship(back_populates="trip")
    live_state: Mapped[TripLiveState | None] = relationship(back_populates="trip", uselist=False)
    location_pings: Mapped[list[TripLocationPing]] = relationship(back_populates="trip")


class TripSeat(Base):
    __tablename__ = "trip_seats"
    __table_args__ = (UniqueConstraint("trip_id", "bus_seat_id", name="uq_trip_bus_seat"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    bus_seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bus_seats.id"), nullable=False)
    status: Mapped[SeatInventoryStatus] = mapped_column(
        Enum(SeatInventoryStatus, name="seat_inventory_status"),
        default=SeatInventoryStatus.AVAILABLE,
        nullable=False,
    )
    hold_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seat_holds.id"))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))

    trip: Mapped[Trip] = relationship(back_populates="inventory")
    bus_seat: Mapped[BusSeat] = relationship()


class SeatHold(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (Index("ix_seat_holds_token", "token", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    fare_paise: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    trip: Mapped[Trip] = relationship()
    seats: Mapped[list[SeatHoldSeat]] = relationship(back_populates="hold", cascade="all, delete-orphan")


class SeatHoldSeat(Base):
    __tablename__ = "seat_hold_seats"
    __table_args__ = (UniqueConstraint("hold_id", "bus_seat_id", name="uq_hold_seat"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hold_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seat_holds.id"), nullable=False)
    bus_seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bus_seats.id"), nullable=False)

    hold: Mapped[SeatHold] = relationship(back_populates="seats")
    bus_seat: Mapped[BusSeat] = relationship()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_pnr", "pnr", unique=True),
        Index("ix_bookings_public_ref", "public_reference", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_reference: Mapped[str] = mapped_column(String(40), nullable=False)
    pnr: Mapped[str | None] = mapped_column(String(12))
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    customer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_users.id"))
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(180), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    pickup_stop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_stops.id"))
    dropoff_stop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_stops.id"))
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="online", server_default="online")
    offline_method: Mapped[str | None] = mapped_column(String(30))
    confirmed_payment_id: Mapped[str | None] = mapped_column(String(80))
    staff_request_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    policy_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    pickup_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    dropoff_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    booking_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.PENDING_PAYMENT,
    )
    access_token: Mapped[str] = mapped_column(String(64), nullable=False)
    hold_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seat_holds.id"))
    verification_code: Mapped[str | None] = mapped_column(String(128))
    exception_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer_user: Mapped[CustomerUser | None] = relationship(back_populates="bookings")
    trip: Mapped[Trip] = relationship(back_populates="bookings")
    pickup_stop: Mapped[RouteStop | None] = relationship(foreign_keys=[pickup_stop_id])
    dropoff_stop: Mapped[RouteStop | None] = relationship(foreign_keys=[dropoff_stop_id])
    seats: Mapped[list[BookingSeat]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    payment_orders: Mapped[list[PaymentOrder]] = relationship(back_populates="booking")
    cancellations: Mapped[list[CancellationRequest]] = relationship(back_populates="booking")


class BookingSeat(Base):
    __tablename__ = "booking_seats"
    __table_args__ = (
        Index(
            "uq_active_booking_seat",
            "trip_id",
            "bus_seat_id",
            unique=True,
            postgresql_where=text("released IS FALSE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    bus_seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bus_seats.id"), nullable=False)
    passenger_name: Mapped[str] = mapped_column(String(120), nullable=False)
    passenger_age: Mapped[int] = mapped_column(Integer, nullable=False)
    passenger_gender: Mapped[str] = mapped_column(String(20), nullable=False)
    fare_snapshot_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    released: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped[Booking] = relationship(back_populates="seats")
    bus_seat: Mapped[BusSeat] = relationship()


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (Index("ix_payment_orders_gateway", "gateway_order_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    gateway_order_id: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[PaymentOrderStatus] = mapped_column(
        Enum(PaymentOrderStatus, name="payment_order_status"),
        default=PaymentOrderStatus.CREATED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    booking: Mapped[Booking] = relationship(back_populates="payment_orders")
    transactions: Mapped[list[PaymentTransaction]] = relationship(back_populates="order")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (Index("ix_payment_txn_gateway", "gateway_payment_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_orders.id"), nullable=False)
    gateway_payment_id: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentTransactionStatus] = mapped_column(
        Enum(PaymentTransactionStatus, name="payment_transaction_status")
    )
    method: Mapped[str | None] = mapped_column(String(40))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[PaymentOrder] = relationship(back_populates="transactions")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_event"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CancellationRequest(Base):
    __tablename__ = "cancellation_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    estimated_refund_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CancellationStatus] = mapped_column(
        Enum(CancellationStatus, name="cancellation_status"),
        default=CancellationStatus.REQUESTED,
    )
    policy_version: Mapped[str] = mapped_column(String(40), default="")
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    booking: Mapped[Booking] = relationship(back_populates="cancellations")
    refunds: Mapped[list[Refund]] = relationship(back_populates="cancellation")


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cancellation_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cancellation_requests.id"), nullable=False)
    payment_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_transactions.id"))
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    gateway_refund_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"),
        default=RefundStatus.REQUESTED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    cancellation: Mapped[CancellationRequest] = relationship(back_populates="refunds")


class CustomerUser(Base):
    __tablename__ = "customer_users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_customer_email"),
        UniqueConstraint("phone", name="uq_customer_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="customer_user")


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (UniqueConstraint("email", name="uq_admin_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(180), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TripLiveState(Base):
    __tablename__ = "trip_live_states"

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), primary_key=True)
    status: Mapped[TrackingStatus] = mapped_column(
        Enum(TrackingStatus, name="tracking_status"),
        default=TrackingStatus.SCHEDULED,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    heading: Mapped[float] = mapped_column(Float, default=0)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(40), default="schedule_estimate")
    next_landmark: Mapped[str] = mapped_column(String(160), default="")
    eta_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_ping_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    simulator_active: Mapped[bool] = mapped_column(Boolean, default=False)
    simulator_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    simulator_duration_seconds: Mapped[int] = mapped_column(Integer, default=360)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="live_state")


class TripLocationPing(Base):
    __tablename__ = "trip_location_pings"
    __table_args__ = (Index("ix_trip_pings_trip_time", "trip_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    heading: Mapped[float] = mapped_column(Float, default=0)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(40), default="gps")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="location_pings")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeatLayout(Base):
    __tablename__ = "seat_layouts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    seats: Mapped[list[dict]] = mapped_column(JSONB)


class RecurringSchedule(Base):
    __tablename__ = "recurring_schedules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"))
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    last_error: Mapped[str | None] = mapped_column(String(255))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
