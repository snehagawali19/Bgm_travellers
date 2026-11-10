"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api, Booking, TrackableTrip } from "@/lib/api";
import { formatIST } from "@/lib/format";

export default function TrackLookupPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<TrackableTrip[]>([]);
  const [pnr, setPnr] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<TrackableTrip[]>("/api/v1/tracking/trips")
      .then(setTrips)
      .catch(() => setError("Could not load live trips. Start the API and seed data first."))
      .finally(() => setLoading(false));
  }, []);

  async function lookup(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const booking = await api<Booking>("/api/v1/bookings/lookup", {
        method: "POST",
        body: JSON.stringify({ pnr, phone }),
      });
      router.push(`/track/${booking.trip.id}?ref=${booking.public_reference}&access_token=${booking.access_token}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Booking not found");
    }
  }

  return (
    <SiteShell>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <p className="text-sm font-medium uppercase tracking-wide text-teal">Live tracking</p>
        <h1 className="mt-2 text-3xl font-semibold text-navy">Track your bus</h1>
        <p className="mt-2 max-w-2xl text-sm text-navy/65">
          Follow the Belgaum ↔ Bengaluru service on the map. Until a GPS device is fitted, the position is a live
          schedule estimate. Admin can push real coordinates or start a demo replay.
        </p>

        <form onSubmit={lookup} className="mt-8 grid gap-3 rounded-2xl border border-neutral-200 bg-white p-5 shadow-[0_12px_40px_rgba(0,0,0,0.08)] md:grid-cols-[1fr_1fr_auto]">
          <input required placeholder="PNR" value={pnr} onChange={(e) => setPnr(e.target.value)} className="rounded-lg border border-neutral-300 bg-white px-3 py-3" />
          <input required placeholder="Mobile number" value={phone} onChange={(e) => setPhone(e.target.value)} className="rounded-lg border border-neutral-300 bg-white px-3 py-3" />
          <button className="rounded-lg bg-brand px-5 py-3 font-bold text-black">Track ticket</button>
        </form>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        <h2 className="mt-10 text-xl font-semibold text-navy">Published services</h2>
        {loading ? <p className="mt-4 text-navy/60">Loading trips…</p> : null}
        <div className="mt-4 space-y-3">
          {trips.map((trip) => (
            <Link
              key={trip.trip_id}
              href={`/track/${trip.trip_id}`}
              className="block rounded-2xl border border-neutral-200 bg-white p-5 hover:border-brand"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-navy">{trip.route_name}</p>
                  <p className="text-sm text-navy/60">
                    {trip.bus_name} · {formatIST(trip.departure_datetime)} · {trip.next_landmark || "Boarding"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium capitalize text-teal">{trip.status.replaceAll("_", " ")}</p>
                  <p className="text-xs text-navy/50">{trip.progress_percent}% of the journey</p>
                </div>
              </div>
            </Link>
          ))}
          {!loading && trips.length === 0 ? (
            <p className="rounded-3xl border border-dashed border-navy/20 bg-white p-8 text-center text-navy/60">
              No published trips to track yet.
            </p>
          ) : null}
        </div>
      </div>
    </SiteShell>
  );
}
