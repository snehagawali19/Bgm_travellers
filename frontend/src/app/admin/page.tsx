"use client";

import { useEffect, useState } from "react";
import { api, Booking, TripCard } from "@/lib/api";
import { formatPaise } from "@/lib/format";

export default function AdminHome() {
  const [trips, setTrips] = useState<TripCard[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);

  useEffect(() => {
    api<TripCard[]>("/api/v1/admin/trips").then(setTrips).catch(() => undefined);
    api<Booking[]>("/api/v1/admin/bookings").then(setBookings).catch(() => undefined);
  }, []);

  const confirmed = bookings.filter((item) => item.status === "confirmed");
  const exceptions = bookings.filter((item) => item.status === "exception");

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Operations</h1>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl bg-white p-5 border border-navy/10"><p className="text-sm text-navy/60">Published trips</p><p className="mt-2 text-3xl font-semibold">{trips.length}</p></article>
        <article className="rounded-2xl bg-white p-5 border border-navy/10"><p className="text-sm text-navy/60">Confirmed bookings</p><p className="mt-2 text-3xl font-semibold">{confirmed.length}</p></article>
        <article className="rounded-2xl bg-white p-5 border border-navy/10"><p className="text-sm text-navy/60">Payment exceptions</p><p className="mt-2 text-3xl font-semibold">{exceptions.length}</p></article>
      </div>
      <p className="mt-8 text-sm text-navy/60">
        Revenue snapshot: {formatPaise(confirmed.reduce((sum, item) => sum + item.total_amount_paise, 0))} from confirmed tickets.
      </p>
    </div>
  );
}
