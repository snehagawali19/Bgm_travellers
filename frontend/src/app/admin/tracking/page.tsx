"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, TrackableTrip } from "@/lib/api";
import { formatIST } from "@/lib/format";

export default function AdminTrackingList() {
  const [trips, setTrips] = useState<TrackableTrip[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<TrackableTrip[]>("/api/v1/admin/tracking")
      .then(setTrips)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load tracking"));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Live tracking</h1>
      <p className="mt-2 text-sm text-navy/60">Push GPS pings or start a 6-minute demo replay of the corridor.</p>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-6 space-y-3">
        {trips.map((trip) => (
          <article key={trip.trip_id} className="flex flex-wrap items-center justify-between rounded-2xl border border-navy/10 bg-white p-4">
            <div>
              <p className="font-medium text-navy">{trip.route_name}</p>
              <p className="text-sm text-navy/60">
                {formatIST(trip.departure_datetime)} · {trip.status.replaceAll("_", " ")} · {trip.progress_percent}%
              </p>
            </div>
            <Link href={`/admin/tracking/${trip.trip_id}`} className="text-sm text-teal">
              Open map
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
