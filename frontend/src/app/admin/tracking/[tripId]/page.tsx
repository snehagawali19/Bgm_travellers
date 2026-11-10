"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, TrackingSnapshot } from "@/lib/api";

const TrackingMap = dynamic(() => import("@/components/TrackingMap").then((mod) => mod.TrackingMap), { ssr: false });

export default function AdminTripTracking() {
  const { tripId } = useParams<{ tripId: string }>();
  const [live, setLive] = useState<TrackingSnapshot | null>(null);
  const [message, setMessage] = useState("");
  const [lat, setLat] = useState("15.8497");
  const [lng, setLng] = useState("74.4977");

  async function load() {
    const data = await api<TrackingSnapshot>(`/api/v1/admin/trips/${tripId}/tracking`);
    setLive(data);
    setLat(String(data.latitude));
    setLng(String(data.longitude));
  }

  useEffect(() => {
    load().catch(() => undefined);
    const timer = setInterval(() => load().catch(() => undefined), 8000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId]);

  async function ping(event: React.FormEvent) {
    event.preventDefault();
    const data = await api<TrackingSnapshot>(`/api/v1/admin/trips/${tripId}/tracking/ping`, {
      method: "POST",
      body: JSON.stringify({ latitude: Number(lat), longitude: Number(lng), speed_kmh: 64 }),
    });
    setLive(data);
    setMessage("GPS ping saved.");
  }

  async function simulate(action: "start" | "stop") {
    const data = await api<TrackingSnapshot>(`/api/v1/admin/trips/${tripId}/tracking/simulate`, {
      method: "POST",
      body: JSON.stringify({ action, duration_seconds: 360 }),
    });
    setLive(data);
    setMessage(action === "start" ? "Demo replay started (6 minutes for the full corridor)." : "Demo replay stopped.");
  }

  if (!live) return <p>Loading tracking…</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">{live.route_name}</h1>
      <p className="mt-1 text-sm capitalize text-navy/60">
        {live.status.replaceAll("_", " ")} · {live.source_label}
      </p>
      <div className="mt-4">
        <TrackingMap
          key={live.trip_id}
          polyline={live.polyline}
          origin={live.origin}
          destination={live.destination}
          position={{ lat: live.latitude, lng: live.longitude, heading: live.heading }}
        />
      </div>
      <form onSubmit={ping} className="mt-6 grid gap-3 rounded-2xl border border-navy/10 bg-white p-4 md:grid-cols-3">
        <input className="rounded-xl border px-3 py-2" value={lat} onChange={(e) => setLat(e.target.value)} />
        <input className="rounded-xl border px-3 py-2" value={lng} onChange={(e) => setLng(e.target.value)} />
        <button className="rounded-lg bg-brand font-bold text-black">Push GPS ping</button>
      </form>
      <div className="mt-3 flex gap-3">
        <button onClick={() => simulate("start")} className="rounded-lg bg-brand px-4 py-2 text-sm font-bold text-black">
          Start demo replay
        </button>
        <button onClick={() => simulate("stop")} className="rounded-xl border border-navy/15 px-4 py-2 text-sm">
          Stop demo
        </button>
      </div>
      {message ? <p className="mt-3 text-sm text-teal">{message}</p> : null}
    </div>
  );
}
