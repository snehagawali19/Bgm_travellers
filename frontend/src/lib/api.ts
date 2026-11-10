const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : "";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = readCookie("bgm_csrf");
  if (csrf) headers.set("X-CSRF-Token", csrf);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_URL}. Start PostgreSQL and the FastAPI server on port 8000.`,
      0,
      "network",
    );
  }

  const text = await response.text();
  let data: { detail?: string; code?: string } | null = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError(text.slice(0, 200) || "Request failed", response.status);
    }
  }
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : "Request failed";
    throw new ApiError(message, response.status, data?.code);
  }
  return data as T;
}

export type City = {
  id: string;
  name: string;
  slug: string;
  state: string;
  aliases: string[];
};

export type Stop = {
  id: string;
  stop_name: string;
  address: string;
  landmark: string;
  offset_minutes: number;
  stop_datetime: string | null;
  pickup_allowed: boolean;
  dropoff_allowed: boolean;
};

export type TripCard = {
  id: string;
  route_id: string;
  booking_cutoff_minutes: number;
  route_name: string;
  origin_name: string;
  destination_name: string;
  departure_datetime: string;
  estimated_arrival_datetime: string;
  duration_minutes: number;
  base_fare_paise: number;
  bus_id: string;
  bus_name: string;
  bus_type: string;
  amenities: string[];
  available_seats: number;
  total_seats: number;
  pickup_stops: Stop[];
  dropoff_stops: Stop[];
  status: string;
};

export type Seat = {
  id: string;
  seat_number: string;
  seat_type: string;
  row_no: number;
  col_no: number;
  deck: string;
  status: string;
};

export type PaymentInfo = {
  provider: string;
  key_id: string | null;
  order_id: string;
  amount_paise: number;
  currency: string;
  booking_public_reference: string;
  access_token: string;
};

export type Customer = {
  id: string;
  email: string;
  phone: string;
  name: string;
};

export type Booking = {
  public_reference: string;
  pnr: string | null;
  status: string;
  channel: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  total_amount_paise: number;
  trip: TripCard;
  seats: Array<{
    id: string;
    checked_in_at: string | null;
    seat_id: string;
    seat_number: string;
    passenger_name: string;
    passenger_age: number;
    passenger_gender: string;
    fare_paise: number;
  }>;
  pickup_stop: Stop | null;
  dropoff_stop: Stop | null;
  access_token: string | null;
  verification_code: string | null;
  exception_reason: string | null;
  payment: PaymentInfo | null;
  cancellation_disclaimer: string | null;
  created_at: string;
};

export type GeoPoint = { lat: number; lng: number; name?: string; at?: string | null };

export type TrackingSnapshot = {
  trip_id: string;
  route_name: string;
  bus_name: string;
  origin_name: string;
  destination_name: string;
  departure_datetime: string;
  estimated_arrival_datetime: string;
  status: string;
  source: string;
  source_label: string;
  latitude: number;
  longitude: number;
  heading: number;
  speed_kmh: number;
  progress_percent: number;
  next_landmark: string;
  eta_minutes: number;
  distance_km: number;
  remaining_km: number;
  polyline: GeoPoint[];
  origin: GeoPoint;
  destination: GeoPoint;
  trail: GeoPoint[];
  last_updated_at: string;
  simulator_active: boolean;
};

export type TrackableTrip = {
  trip_id: string;
  route_name: string;
  bus_name: string;
  origin_name: string;
  destination_name: string;
  departure_datetime: string;
  status: string;
  progress_percent: number;
  next_landmark: string;
  source_label: string;
};
