"use client";

import { useEffect, useState } from "react";
import { api, TripCard } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";

export default function TripsPage() {
  const [trips, setTrips] = useState<TripCard[]>([]);
  const [buses, setBuses] = useState<Array<{ id: string; display_name: string }>>([]);
  const [routes, setRoutes] = useState<Array<{ id: string; route_name: string }>>([]);
  const [owner, setOwner] = useState(false);
  const [editing, setEditing] = useState("");
  const [form, setForm] = useState({
    route_id: "",
    bus_id: "",
    departure_datetime: "",
    estimated_arrival_datetime: "",
    base_fare_paise: 89900,
    booking_cutoff_minutes: 60,
    status: "published",
  });
  const [error, setError] = useState("");

  async function load() {
    setTrips(await api("/api/v1/admin/trips"));
    setBuses(await api("/api/v1/admin/buses"));
    setRoutes(await api("/api/v1/admin/routes"));
  }

  useEffect(() => {
    load().catch(e => setError(e.message));
    api<{ role: string }>("/api/v1/admin/auth/me").then(u => setOwner(u.role !== "booking_staff"));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Trips</h1>
      {owner && <form
        className="mt-6 grid gap-3 rounded-2xl border border-navy/10 bg-white p-4 md:grid-cols-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setError("");
          try {
            await api(`/api/v1/admin/trips${editing ? `/${editing}` : ""}`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(form) });
            setEditing("");
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Could not create trip");
          }
        }}
      >
        <select className="rounded-xl border px-3 py-2" value={form.route_id} onChange={(e) => setForm({ ...form, route_id: e.target.value })}>
          <option value="">Route</option>
          {routes.map((route) => <option key={route.id} value={route.id}>{route.route_name}</option>)}
        </select>
        <select className="rounded-xl border px-3 py-2" value={form.bus_id} onChange={(e) => setForm({ ...form, bus_id: e.target.value })}>
          <option value="">Bus</option>
          {buses.map((bus) => <option key={bus.id} value={bus.id}>{bus.display_name}</option>)}
        </select>
        <input className="rounded-xl border px-3 py-2" placeholder="Fare paise" type="number" value={form.base_fare_paise} onChange={(e) => setForm({ ...form, base_fare_paise: Number(e.target.value) })} />
        <input className="rounded-xl border px-3 py-2" type="datetime-local" value={form.departure_datetime} onChange={(e) => setForm({ ...form, departure_datetime: e.target.value })} />
        <input className="rounded-xl border px-3 py-2" type="datetime-local" value={form.estimated_arrival_datetime} onChange={(e) => setForm({ ...form, estimated_arrival_datetime: e.target.value })} />
        <label className="text-sm">Booking closes before departure (minutes)<input className="w-full rounded-xl border px-3 py-2" type="number" min={0} value={form.booking_cutoff_minutes} onChange={e => setForm({ ...form, booking_cutoff_minutes: Number(e.target.value) })} /></label>
        {!editing && <label className="text-sm">Initial status<select className="w-full rounded-xl border px-3 py-2" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option value="published">Published</option><option value="draft">Draft</option></select></label>}
        <button className="rounded-lg bg-brand p-3 font-bold text-black">{editing ? "Save departure changes" : "Create departure"}</button>
        {editing && <button type="button" className="underline" onClick={() => setEditing("")}>Cancel editing</button>}
      </form>}
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-6 space-y-3">
        {trips.map((trip) => (
          <article key={trip.id} className="flex flex-wrap items-center justify-between rounded-2xl border border-navy/10 bg-white p-4">
            <div>
              <p className="font-medium text-navy">{trip.route_name}</p>
              <p className="text-sm font-semibold">{trip.status}</p>
              <p className="text-sm text-navy/60">{formatIST(trip.departure_datetime)} · {trip.bus_name} · {formatPaise(trip.base_fare_paise)} · {trip.available_seats}/{trip.total_seats} open</p>
            </div>
            <div className="flex gap-3 text-sm">
              <a className="underline" href={`/admin/trips/${trip.id}/manage`}>Seats and check-in</a>
              <a className="text-teal" href={`/admin/tracking/${trip.id}`}>Track</a>
              <a className="text-teal" href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/admin/trips/${trip.id}/manifest`}>CSV</a>
              {owner && !["cancelled", "completed"].includes(trip.status) && <>
              <button className="underline" onClick={() => { setEditing(trip.id); const local = (value: string) => new Date(value).toLocaleString("sv-SE", { timeZone: "Asia/Kolkata" }).replace(" ", "T").slice(0, 16); setForm({ route_id: trip.route_id, bus_id: trip.bus_id, departure_datetime: local(trip.departure_datetime), estimated_arrival_datetime: local(trip.estimated_arrival_datetime), base_fare_paise: trip.base_fare_paise, booking_cutoff_minutes: trip.booking_cutoff_minutes, status: "published" }); }}>Edit</button>
              <button className="underline" onClick={async () => { try { await api(`/api/v1/admin/trips/${trip.id}/${trip.status === "published" ? "close" : "publish"}`, { method: "POST" }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Update failed"); } }}>{trip.status === "published" ? "Close bookings" : "Publish"}</button>
              <button
                className="text-red-700"
                onClick={async () => {
                  if (!window.confirm("Cancel this departure and queue full refunds for its passengers?")) return;
                  try { await api(`/api/v1/admin/trips/${trip.id}/cancel`, { method: "POST" }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Cancellation failed"); }
                }}
              >
                Cancel trip
              </button>
              </>}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
