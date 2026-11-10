"use client";

import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api, TrackingSnapshot } from "@/lib/api";
import { formatIST } from "@/lib/format";

const TrackingMap = dynamic(() => import("@/components/TrackingMap").then((mod) => mod.TrackingMap), {
  ssr: false,
  loading: () => <div className="h-[420px] animate-pulse rounded-3xl bg-sand" />,
});

export default function LiveTrackPage() {
  const { tripId } = useParams<{ tripId: string }>();
  const params = useSearchParams();
  const access = params.get("access_token");
  const ref = params.get("ref");
  const [live, setLive] = useState<TrackingSnapshot | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const path = ref
          ? `/api/v1/bookings/${ref}/tracking?access_token=${access || ""}`
          : `/api/v1/trips/${tripId}/tracking`;
        setLive(await api<TrackingSnapshot>(path));
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load tracking");
      }
    }
    load();
    const timer = setInterval(load, 8000);
    return () => clearInterval(timer);
  }, [tripId, access, ref]);

  return (
    <SiteShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        {error ? <p className="mb-4 text-sm text-red-700">{error}</p> : null}
        {live ? (
          <>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-teal">{live.bus_name}</p>
                <h1 className="text-3xl font-semibold text-navy">
                  {live.origin_name} → {live.destination_name}
                </h1>
                <p className="text-sm text-navy/60">
                  Departs {formatIST(live.departure_datetime)} · arrives {formatIST(live.estimated_arrival_datetime)}
                </p>
              </div>
              <div className="rounded-2xl bg-white px-4 py-3 text-right shadow-sm">
                <p className="text-xs uppercase tracking-wide text-navy/50">Status</p>
                <p className="font-semibold capitalize text-navy">{live.status.replaceAll("_", " ")}</p>
              </div>
            </div>
            <TrackingMap
              key={live.trip_id}
              polyline={live.polyline}
              origin={live.origin}
              destination={live.destination}
              position={{ lat: live.latitude, lng: live.longitude, heading: live.heading }}
            />
            <div className="mt-6 grid gap-4 md:grid-cols-4">
              {[
                ["Next landmark", live.next_landmark || "—"],
                ["Progress", `${live.progress_percent}%`],
                ["ETA", live.eta_minutes ? `${live.eta_minutes} min` : "Arrived / at depot"],
                ["Remaining", `${live.remaining_km} km`],
              ].map(([label, value]) => (
                <article key={label} className="rounded-2xl border border-navy/10 bg-white p-4">
                  <p className="text-xs uppercase tracking-wide text-navy/50">{label}</p>
                  <p className="mt-1 font-semibold text-navy">{value}</p>
                </article>
              ))}
            </div>
            <p className="mt-4 text-xs text-navy/50">{live.source_label}. Map refreshes every few seconds.</p>
          </>
        ) : !error ? (
          <p className="text-navy/60">Connecting to live tracking…</p>
        ) : null}
      </div>
    </SiteShell>
  );
}
