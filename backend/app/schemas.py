from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

GENDER = Literal["male", "female", "other"]


class CityOut(BaseModel):
    id: UUID
    name: str
    slug: str
    state: str
    country: str
    latitude: float | None = None
    longitude: float | None = None
    active: bool
    aliases: list[str] = []

    model_config = {"from_attributes": True}


class CityIn(BaseModel):
    name: str
    slug: str
    state: str
    country: str = "India"
    latitude: float | None = None
    longitude: float | None = None
    active: bool = True
    aliases: list[str] = []


class StopOut(BaseModel):
    id: UUID
    stop_name: str
    address: str
    landmark: str = ""
    offset_minutes: int = 0
    stop_datetime: datetime | None = None
    pickup_allowed: bool
    dropoff_allowed: bool
    display_order: int
    active: bool

    model_config = {"from_attributes": True}


class RouteOut(BaseModel):
    id: UUID
    origin_city_id: UUID
    destination_city_id: UUID
    origin_name: str
    destination_name: str
    route_name: str
    estimated_duration_minutes: int
    active: bool
    stops: list[StopOut] = []


class RouteIn(BaseModel):
    origin_city_id: UUID
    destination_city_id: UUID
    route_name: str
    estimated_duration_minutes: int
    active: bool = True


class StopIn(BaseModel):
    city_id: UUID | None = None
    stop_name: str
    address: str = ""
    landmark: str = Field(default="", max_length=255)
    offset_minutes: int = Field(default=0, ge=0, le=4320)
    pickup_allowed: bool = True
    dropoff_allowed: bool = True
    display_order: int = 0
    active: bool = True


class BusSeatOut(BaseModel):
    id: UUID
    seat_number: str
    seat_type: str
    row_no: int
    col_no: int
    deck: str
    active: bool

    model_config = {"from_attributes": True}


class BusOut(BaseModel):
    id: UUID
    registration_number: str
    display_name: str
    bus_type: str
    seat_capacity: int
    status: str
    amenities: list[str]
    seats: list[BusSeatOut] = []

    model_config = {"from_attributes": True}


class BusIn(BaseModel):
    registration_number: str
    display_name: str
    bus_type: Literal["seater", "sleeper", "semi_sleeper"] = "seater"
    seat_capacity: int
    status: Literal["active", "maintenance", "retired"] = "active"
    amenities: list[str] = []


class SeatLayoutIn(BaseModel):
    seat_number: str = Field(min_length=1, max_length=20)
    seat_type: Literal["window", "aisle", "single"] = "aisle"
    row_no: int = Field(ge=1, le=100)
    col_no: int = Field(ge=1, le=20)
    deck: Literal["lower", "upper"] = "lower"
    active: bool = True


class TripSearchQuery(BaseModel):
    origin_city_id: UUID
    destination_city_id: UUID
    travel_date: str
    passengers: int = Field(ge=1, le=10, default=1)


class TripCardOut(BaseModel):
    id: UUID
    route_id: UUID
    route_name: str
    origin_name: str
    destination_name: str
    departure_datetime: datetime
    estimated_arrival_datetime: datetime
    duration_minutes: int
    base_fare_paise: int
    bus_id: UUID
    bus_name: str
    bus_type: str
    amenities: list[str]
    available_seats: int
    total_seats: int
    pickup_stops: list[StopOut]
    dropoff_stops: list[StopOut]
    status: str
    booking_cutoff_minutes: int = 60


class SeatMapSeat(BaseModel):
    id: UUID
    seat_number: str
    seat_type: str
    row_no: int
    col_no: int
    deck: str
    status: str


class TripSeatMapOut(BaseModel):
    trip: TripCardOut
    seats: list[SeatMapSeat]
    hold_ttl_minutes: int
    cancellation_disclaimer: str | None = None


class HoldIn(BaseModel):
    trip_id: UUID
    seat_ids: list[UUID] = Field(min_length=1, max_length=10)


class HoldOut(BaseModel):
    hold_token: str
    trip_id: UUID
    seat_numbers: list[str]
    expires_at: datetime
    fare_paise: int


class PassengerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=1, le=120)
    gender: GENDER
    seat_id: UUID


class BookingCreateIn(BaseModel):
    hold_token: str
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: EmailStr
    customer_phone: str
    pickup_stop_id: UUID
    dropoff_stop_id: UUID
    passengers: list[PassengerIn] = Field(min_length=1, max_length=10)

    @field_validator("customer_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return digits


class PaymentOrderOut(BaseModel):
    provider: str
    key_id: str | None
    order_id: str
    amount_paise: int
    currency: str
    booking_public_reference: str
    access_token: str


class BookingOut(BaseModel):
    public_reference: str
    pnr: str | None
    status: str
    customer_name: str
    customer_email: str
    customer_phone: str
    total_amount_paise: int
    trip: TripCardOut
    seats: list[dict[str, Any]]
    pickup_stop: StopOut | None
    dropoff_stop: StopOut | None
    access_token: str | None = None
    verification_code: str | None = None
    exception_reason: str | None = None
    payment: PaymentOrderOut | None = None
    cancellation_disclaimer: str | None = None
    created_at: datetime


class PaymentVerifyIn(BaseModel):
    public_reference: str
    gateway_order_id: str
    gateway_payment_id: str
    gateway_signature: str


class LookupIn(BaseModel):
    pnr: str
    phone: str


class CancelIn(BaseModel):
    reason: str = "Customer requested cancellation"


class RefundEstimateOut(BaseModel):
    eligible: bool
    estimated_refund_paise: int
    policy_version: str
    disclaimer: str
    breakdown: dict[str, Any]


class TripIn(BaseModel):
    route_id: UUID
    bus_id: UUID
    departure_datetime: datetime
    estimated_arrival_datetime: datetime
    base_fare_paise: int = Field(gt=0)
    booking_cutoff_minutes: int = Field(default=60, ge=0, le=10080)
    cancellation_policy_id: UUID | None = None
    status: Literal["draft", "published"] = "draft"

    @field_validator("departure_datetime", "estimated_arrival_datetime")
    @classmethod
    def assume_ist(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            from zoneinfo import ZoneInfo

            return value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return value


class BlockSeatsIn(BaseModel):
    seat_ids: list[UUID]
    blocked: bool = True


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


class CustomerRegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str
    password: str = Field(min_length=6, max_length=120)

    @field_validator("phone")
    @classmethod
    def validate_customer_phone(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return digits


class CustomerLoginIn(BaseModel):
    email: EmailStr
    password: str


class CustomerOut(BaseModel):
    id: UUID
    email: str
    phone: str
    name: str


class AdminUserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str


class TrackingPingIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    heading: float = 0
    speed_kmh: float = Field(ge=0, le=140, default=0)
    status: Literal["scheduled", "boarding", "departed", "in_transit", "arriving", "completed"] | None = None


class SimulatorIn(BaseModel):
    action: Literal["start", "stop"]
    duration_seconds: int = Field(ge=60, le=7200, default=360)


class LayoutTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    seats: list[SeatLayoutIn] = Field(min_length=1, max_length=100)


class ScheduleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    route_id: UUID
    bus_id: UUID
    departure_time: time
    duration_minutes: int = Field(gt=0, le=4320)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    base_fare_paise: int = Field(gt=0)
    booking_cutoff_minutes: int = Field(default=60, ge=0, le=10080)
    cancellation_policy_id: UUID | None = None
    active: bool = True

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, values):
        if len(set(values)) != len(values) or any(v < 0 or v > 6 for v in values):
            raise ValueError("Weekdays must be unique: Monday=0 through Sunday=6")
        return values


class GenerateTripsIn(BaseModel):
    start_date: date
    end_date: date
    publish: bool = True


class CounterBookingIn(BookingCreateIn):
    hold_token: str = ""
    trip_id: UUID
    channel: Literal["counter", "phone"] = "counter"
    payment_method: Literal["cash", "upi", "bank_transfer"]
    payment_reference: str = Field(default="", max_length=120)
    request_id: UUID


class SwapBusIn(BaseModel):
    bus_id: UUID
    seat_mapping: dict[UUID, UUID] = {}


class StaffIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=72)
    role: Literal["owner", "booking_staff"] = "booking_staff"


class RefundRuleIn(BaseModel):
    min_hours_before_departure: int = Field(ge=0)
    refund_percent: int = Field(ge=0, le=100)


class PolicyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    cutoff_minutes: int = Field(default=60, ge=0)
    rules: list[RefundRuleIn] = Field(min_length=1)
    disclaimer: str = ""
