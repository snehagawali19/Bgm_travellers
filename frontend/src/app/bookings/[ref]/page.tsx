"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import RetryPayment from "@/components/RetryPayment";
import { api, Booking } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function TicketPage() {
  const { ref } = useParams<{ ref: string }>();
  const params = useSearchParams();
  const access = params.get("access_token") || "";
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const data = await api<Booking>(`/api/v1/bookings/${ref}?access_token=${access}`);
      setBooking(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load booking");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, access]);

  async function cancel() {
    if (!booking) return;
    setMessage("");
    try {
      const estimate = await api<{ estimated_refund_paise: number; disclaimer: string }>(
        `/api/v1/bookings/${ref}/refund-estimate?access_token=${access}`,
      );
      const ok = window.confirm(`Estimated refund ${formatPaise(estimate.estimated_refund_paise)}. ${estimate.disclaimer}`);
      if (!ok) return;
      const updated = await api<Booking>(`/api/v1/bookings/${ref}/cancel?access_token=${access}`, {
        method: "POST",
        body: JSON.stringify({ reason: "Customer requested cancellation" }),
      });
      setBooking(updated);
      setMessage("Cancellation submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancellation failed");
    }
  }

  return (
    <SiteShell>
      <div className="mx-auto max-w-3xl px-4 py-10">
        {error ? <p className="text-red-700">{error}</p> : null}
        {booking ? (
          <article className="ticket-print rounded-3xl border border-navy/10 bg-white p-8">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm uppercase tracking-wide text-teal">BGM Travels e-ticket</p>
                <h1 className="mt-1 text-3xl font-semibold text-navy">{booking.pnr || "Payment pending"}</h1>
                <p className="text-sm text-navy/60">Status: {booking.status.replaceAll("_", " ")}</p>
              </div>
              {booking.verification_code ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  alt="Ticket QR"
                  src={`${API_URL}/api/v1/bookings/${booking.public_reference}/ticket.png?access_token=${access}`}
                  className="h-28 w-28"
                />
              ) : null}
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 text-sm">
              <p><strong>Route:</strong> {booking.trip.origin_name} → {booking.trip.destination_name}</p>
              <p><strong>Departure:</strong> {formatIST(booking.trip.departure_datetime)}</p>
              <p><strong>Pickup:</strong> {booking.pickup_stop?.stop_name}</p>
              <p><strong>Drop:</strong> {booking.dropoff_stop?.stop_name}</p>
              <p><strong>Boarding address:</strong> {booking.pickup_stop?.address} {booking.pickup_stop?.landmark ? ` · ${booking.pickup_stop.landmark}` : ""}</p>
              <p><strong>Boarding time:</strong> {booking.pickup_stop?.stop_datetime ? formatIST(booking.pickup_stop.stop_datetime) : formatIST(booking.trip.departure_datetime)}. Arrive 15 minutes early.</p>
              <p><strong>Passenger contact:</strong> {booking.customer_name}, {booking.customer_phone}</p>
              <p><strong>Amount:</strong> {formatPaise(booking.total_amount_paise)}</p>
            </div>
            <ul className="mt-6 space-y-2 text-sm">
              {booking.seats.map((seat) => (
                <li key={seat.seat_id} className="rounded-xl bg-cream px-4 py-3">
                  {seat.seat_number} · {seat.passenger_name} · {seat.passenger_age} · {seat.passenger_gender}
                </li>
              ))}
            </ul>
            {booking.exception_reason ? (
              <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{booking.exception_reason}</p>
            ) : null}
            {booking.cancellation_disclaimer ? (
              <p className="mt-4 text-xs text-navy/50">{booking.cancellation_disclaimer}</p>
            ) : null}
            {message ? <p className="mt-4 text-sm text-teal">{message}</p> : null}
            <div className="no-print mt-6 flex flex-wrap gap-3">
              {booking.status === "pending_payment" && <RetryPayment booking={booking} access={access} onUpdated={setBooking} />}
              <Link
                href={`/track/${booking.trip.id}?ref=${booking.public_reference}&access_token=${access}`}
                className="rounded-lg bg-brand px-4 py-2 text-sm font-bold text-black"
              >
                Track this bus
              </Link>
              <button onClick={() => window.print()} className="rounded-2xl border border-navy/15 px-4 py-2 text-sm">Print / save PDF</button>
              {booking.status === "confirmed" ? (
                <button onClick={cancel} className="rounded-lg bg-brand px-4 py-2 text-sm font-bold text-black">Request cancellation</button>
              ) : null}
            </div>
          </article>
        ) : null}
      </div>
    </SiteShell>
  );
}
