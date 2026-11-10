"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Field, Notice, control, button, panel, errorText } from "./AdminControls";

type Stop = { id?: string; stop_name: string; address: string; landmark: string; display_order: number; offset_minutes: number; pickup_allowed: boolean; dropoff_allowed: boolean; active: boolean };
const empty: Stop = { stop_name: "", address: "", landmark: "", display_order: 1, offset_minutes: 0, pickup_allowed: true, dropoff_allowed: false, active: true };
export default function RouteStopsEditor({ routeId }: { routeId: string }) {
  const [stops, setStops] = useState<Stop[]>([]);
  const [form, setForm] = useState(empty);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() { const rows = await api<{ id: string; stops: Stop[] }[]>("/api/v1/admin/routes"); setStops((rows.find(r => r.id === routeId)?.stops || []).sort((a, b) => a.display_order - b.display_order)); }
  useEffect(() => { setForm(empty); load().catch(e => setMessage(errorText(e))); }, [routeId]);
  return <section className={`${panel} mt-4`}><h2 className="font-semibold">Boarding and drop-off points</h2><Notice message={message} /><div className="space-y-2">{stops.map(s => <button key={s.id} className="block w-full rounded border p-3 text-left text-sm" onClick={() => setForm(s)}>{s.display_order}. {s.stop_name} · {s.offset_minutes} minutes after departure · {s.pickup_allowed ? "Pickup " : ""}{s.dropoff_allowed ? "Drop-off " : ""} · {s.active ? "active" : "inactive"}<span className="block text-neutral-500">{s.address} · {s.landmark}</span><span className="underline">Edit stop</span></button>)}</div>
    <form className="grid gap-3 md:grid-cols-3" onSubmit={async e => { e.preventDefault(); setBusy(true); try { await api(`/api/v1/admin/routes/${routeId}/stops${form.id ? `/${form.id}` : ""}`, { method: form.id ? "PATCH" : "POST", body: JSON.stringify(form) }); await load(); setForm(empty); setMessage("Stop saved."); } catch (err) { setMessage(errorText(err)); } finally { setBusy(false); } }}>
      <Field label="Stop name"><input required className={control} value={form.stop_name} onChange={e => setForm({ ...form, stop_name: e.target.value })} /></Field><Field label="Address"><input required className={control} value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></Field><Field label="Landmark"><input className={control} value={form.landmark} onChange={e => setForm({ ...form, landmark: e.target.value })} /></Field><Field label="Stop order"><input type="number" min={1} className={control} value={form.display_order} onChange={e => setForm({ ...form, display_order: Number(e.target.value) })} /></Field><Field label="Minutes after departure"><input type="number" min={0} className={control} value={form.offset_minutes} onChange={e => setForm({ ...form, offset_minutes: Number(e.target.value) })} /></Field><div className="flex items-center gap-3">{(["pickup_allowed", "dropoff_allowed", "active"] as const).map(key => <label key={key} className="text-sm"><input type="checkbox" checked={form[key]} onChange={e => setForm({ ...form, [key]: e.target.checked })} />{key === "pickup_allowed" ? "Pickup" : key === "dropoff_allowed" ? "Drop-off" : "Active"}</label>)}</div><button className={button} disabled={busy}>{form.id ? "Save stop" : "Add stop"}</button><button type="button" className="underline" onClick={() => setForm(empty)}>New stop</button>
    </form>
  </section>;
}
