"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { SearchCard } from "@/components/SearchCard";
import { SiteShell } from "@/components/SiteShell";
import { api, TripCard } from "@/lib/api";
import { durationLabel, formatISTTime, formatPaise } from "@/lib/format";

function Results() {
  const params = useSearchParams();
  const origin = params.get("origin") || "";
  const destination = params.get("destination") || "";
  const date = params.get("date") || "";
  const passengers = params.get("passengers") || "1";
  const [trips, setTrips] = useState<TripCard[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!origin || !destination || !date) return;
    setTrips(null);
    api<TripCard[]>(
      `/api/v1/trips/search?origin_city_id=${origin}&destination_city_id=${destination}&travel_date=${date}&passengers=${passengers}`,
    )
      .then(setTrips)
      .catch((err) => setError(err.message));
  }, [origin, destination, date, passengers]);

  return (
    <SiteShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <SearchCard compact initial={{ origin, destination, date, passengers }} />
        <h1 className="mt-8 text-2xl font-semibold text-navy">Available trips</h1>
        <p className="mt-1 text-sm text-navy/60">Results are published operator trips only. Fares and seats are live from the database.</p>
        {error ? <p className="mt-6 text-red-700">{error}</p> : null}
        {trips === null && !error ? <p className="mt-6 text-navy/60">Checking published trips…</p> : null}
        {trips && trips.length === 0 ? (
          <div className="mt-8 rounded-3xl border border-dashed border-navy/20 bg-white p-10 text-center">
            <p className="text-lg font-medium text-navy">No trip published for this date</p>
            <p className="mt-2 text-sm text-navy/60">BGM Travels does not invent availability. Ask the operator to publish a departure, or try another date.</p>
          </div>
        ) : null}
        <div className="mt-6 space-y-4">
          {trips?.map((trip) => (
            <article key={trip.id} className="rounded-2xl border border-neutral-200 bg-white p-5 md:flex md:items-center md:justify-between">
              <div>
                <p className="text-sm font-medium text-teal">{trip.bus_name} · {trip.bus_type}</p>
                <div className="mt-2 flex flex-wrap items-baseline gap-4">
                  <strong className="text-2xl text-navy">{formatISTTime(trip.departure_datetime)}</strong>
                  <span className="text-navy/50">{durationLabel(trip.duration_minutes)}</span>
                  <strong className="text-2xl text-navy">{formatISTTime(trip.estimated_arrival_datetime)}</strong>
                </div>
                <p className="mt-2 text-sm text-navy/70">
                  {trip.origin_name} → {trip.destination_name} · {trip.available_seats} seats left
                </p>
                <p className="mt-1 text-xs text-navy/50">
                  Pickup: {trip.pickup_stops.map((stop) => stop.stop_name).join(", ")}
                </p>
              </div>
              <div className="mt-4 md:mt-0 md:text-right">
                <p className="text-2xl font-semibold text-navy">{formatPaise(trip.base_fare_paise)}</p>
                <p className="text-xs text-navy/50">per passenger</p>
                <Link
                  href={`/trips/${trip.id}?passengers=${passengers}`}
                  className="mt-3 inline-block rounded-lg bg-brand px-4 py-2 text-sm font-bold text-black"
                >
                  Select seats
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </SiteShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <Results />
    </Suspense>
  );
}
