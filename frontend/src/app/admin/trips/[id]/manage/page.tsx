"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Booking, Seat } from "@/lib/api";
import { Field, Notice, control, button, panel, errorText } from "@/components/AdminControls";

type Bus = { id: string; display_name: string; seats: Seat[] };
export default function ManageTrip() {
  const { id } = useParams<{ id: string }>();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [buses, setBuses] = useState<Bus[]>([]);
  const [owner, setOwner] = useState(false);
  const [busId, setBusId] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() { const [b, s] = await Promise.all([api<Booking[]>(`/api/v1/admin/trips/${id}/passengers`), api<Seat[]>(`/api/v1/admin/trips/${id}/inventory`)]); setBookings(b); setSeats(s); }
  useEffect(() => { load().catch(e => setMessage(errorText(e))); api<Bus[]>("/api/v1/admin/buses").then(setBuses).catch(e => setMessage(errorText(e))); api<{ role: string }>("/api/v1/admin/auth/me").then(u => setOwner(u.role !== "booking_staff")); }, [id]);
  async function action(path: string, body: unknown) { setBusy(true); setMessage(""); try { await api(path, { method: "POST", body: JSON.stringify(body) }); await load(); setMessage("Saved."); } catch (e) { setMessage(errorText(e)); } finally { setBusy(false); } }
  const affected = seats.filter(s => ["booked", "blocked"].includes(s.status));
  return <div className="max-w-5xl space-y-5"><h1 className="text-2xl font-semibold">Passenger manifest and seat operations</h1><Notice message={message} />
    <section className={panel}><div className="flex justify-between"><h2 className="font-semibold">Boarding check-in</h2><a className="underline" href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/admin/trips/${id}/manifest`}>Download CSV</a></div>
      {!bookings.length && <p>No confirmed passengers yet.</p>}
      {bookings.map(b => <article className="border-t pt-4" key={b.public_reference}><p className="font-medium">{b.pnr} · {b.customer_phone} · {b.pickup_stop?.stop_name}</p>{b.seats.map(s => <div className="flex flex-wrap items-center justify-between gap-3 py-2" key={s.id}><p>Seat {s.seat_number} · {s.passenger_name} · {s.passenger_age} years</p><button className={button} disabled={busy} onClick={() => action(`/api/v1/admin/booking-seats/${s.id}/check-in`, { checked_in: !s.checked_in_at })}>{s.checked_in_at ? "Checked in — undo" : "Check in"}</button></div>)}</article>)}
    </section>
    <section className={panel}><h2 className="font-semibold">Seat inventory</h2><div className="flex flex-wrap gap-2">{seats.map(s => <button key={s.id} type="button" disabled={!owner || busy || !["available", "blocked"].includes(s.status)} className="rounded-lg border px-4 py-3 text-sm disabled:opacity-50" onClick={() => action(`/api/v1/admin/trips/${id}/block-seats`, { seat_ids: [s.id], blocked: s.status === "available" })}>{s.seat_number}<span className="block text-xs">{s.status}</span>{owner && ["available", "blocked"].includes(s.status) && <span className="block text-xs underline">{s.status === "blocked" ? "Unblock" : "Block"}</span>}</button>)}</div></section>
    {owner && <section className={panel}><h2 className="font-semibold">Replace bus</h2><p className="text-sm text-neutral-600">Choose a distinct replacement for every booked or blocked seat. Active checkouts must finish or expire before this can be applied.</p><Field label="Replacement bus"><select className={control} value={busId} onChange={e => { setBusId(e.target.value); setMapping({}); }}><option value="">Select bus</option>{buses.map(b => <option key={b.id} value={b.id}>{b.display_name}</option>)}</select></Field>
      {busId && affected.map(s => <Field key={s.id} label={`Current seat ${s.seat_number} (${s.status})`}><select className={control} value={mapping[s.id] || ""} onChange={e => setMapping({ ...mapping, [s.id]: e.target.value })}><option value="">Assign replacement seat</option>{buses.find(b => b.id === busId)?.seats.map(t => <option key={t.id} value={t.id} disabled={Object.entries(mapping).some(([key, value]) => key !== s.id && value === t.id)}>{t.seat_number} · {t.seat_type}</option>)}</select></Field>)}
      <button className={button} disabled={busy || !busId || affected.some(s => !mapping[s.id])} onClick={() => action(`/api/v1/admin/trips/${id}/swap-bus`, { bus_id: busId, seat_mapping: mapping })}>Apply bus and seat changes</button>
    </section>}
  </div>;
}
