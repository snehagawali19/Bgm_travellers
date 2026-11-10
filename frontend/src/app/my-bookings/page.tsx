"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api, Booking } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";

type Customer = { id: string; name: string; email: string };

export default function MyBookingsPage() {
  const router = useRouter();
  const [pnr, setPnr] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [bookings, setBookings] = useState<Booking[] | null>(null);

  useEffect(() => {
    api<Customer>("/api/v1/auth/me")
      .then((user) => {
        setCustomer(user);
        return api<Booking[]>("/api/v1/auth/bookings");
      })
      .then((rows) => setBookings(rows))
      .catch(() => {
        setCustomer(null);
        setBookings(null);
      });
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const booking = await api<Booking>("/api/v1/bookings/lookup", {
        method: "POST",
        body: JSON.stringify({ pnr, phone }),
      });
      router.push(`/bookings/${booking.public_reference}?access_token=${booking.access_token}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Booking not found");
    }
  }

  return (
    <SiteShell>
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-semibold text-navy">My bookings</h1>
        {customer ? (
          <p className="mt-2 text-sm text-navy/60">Signed in as {customer.name}. Tickets attached to this account are listed below.</p>
        ) : (
          <p className="mt-2 text-sm text-navy/60">
            <Link href="/login" className="font-semibold text-teal">Sign in</Link> to see saved tickets, or look up a PNR as a guest.
          </p>
        )}

        {bookings && bookings.length > 0 ? (
          <div className="mt-6 space-y-3">
            {bookings.map((booking) => (
              <Link
                key={booking.public_reference}
                href={`/bookings/${booking.public_reference}?access_token=${booking.access_token}`}
                className="block rounded-2xl border border-neutral-200 bg-white p-5 hover:border-brand"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-navy">{booking.trip.origin_name} → {booking.trip.destination_name}</p>
                    <p className="text-sm text-navy/60">
                      {booking.pnr || "Pending PNR"} · {formatIST(booking.trip.departure_datetime)} · {booking.status.replaceAll("_", " ")}
                    </p>
                  </div>
                  <p className="font-semibold">{formatPaise(booking.total_amount_paise)}</p>
                </div>
              </Link>
            ))}
          </div>
        ) : customer ? (
          <p className="mt-6 rounded-2xl border border-dashed border-neutral-300 bg-white p-6 text-sm text-navy/60">
            No tickets on this account yet. Book a trip, or look up an older PNR below.
          </p>
        ) : null}

        <form onSubmit={submit} className="mt-8 space-y-3 rounded-2xl border border-neutral-200 bg-white p-6 shadow-[0_12px_40px_rgba(0,0,0,0.08)]">
          <p className="text-sm font-semibold text-navy">Find a ticket with PNR</p>
          <input required placeholder="PNR" value={pnr} onChange={(e) => setPnr(e.target.value)} className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-3" />
          <input required placeholder="Mobile number" value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-3" />
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <button className="w-full rounded-lg bg-brand py-3 font-bold text-black">Find ticket</button>
        </form>
      </div>
    </SiteShell>
  );
}
