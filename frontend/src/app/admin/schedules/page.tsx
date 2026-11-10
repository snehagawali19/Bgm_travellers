"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Field, Notice, control, button, panel, errorText } from "@/components/AdminControls";

type Definition = { name: string; route_id: string; bus_id: string; departure_time: string; duration_minutes: number; weekdays: number[]; base_fare_paise: number; booking_cutoff_minutes: number; active: boolean };
type Schedule = { id: string; name: string; active: boolean; definition: Definition };
const initial: Definition = { name: "", route_id: "", bus_id: "", departure_time: "21:30", duration_minutes: 510, weekdays: [0, 2, 4], base_fare_paise: 89900, booking_cutoff_minutes: 60, active: true };
export default function SchedulesPage() {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [routes, setRoutes] = useState<{ id: string; route_name: string }[]>([]);
  const [buses, setBuses] = useState<{ id: string; display_name: string }[]>([]);
  const [form, setForm] = useState(initial);
  const [editing, setEditing] = useState("");
  const [range, setRange] = useState({ start_date: "", end_date: "", publish: true });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() { const [s, r, b] = await Promise.all([api<Schedule[]>("/api/v1/admin/schedules"), api<typeof routes>("/api/v1/admin/routes"), api<typeof buses>("/api/v1/admin/buses")]); setRows(s); setRoutes(r); setBuses(b); }
  useEffect(() => { load().catch(e => setMessage(errorText(e))); }, []);
  return <div className="max-w-5xl space-y-5"><h1 className="text-2xl font-semibold">Recurring schedules</h1><p className="text-sm text-neutral-600">Times use India Standard Time. Each generated departure has its own seats. Changes apply to future generation.</p><Notice message={message} />
    <form className={`${panel} grid gap-4 md:grid-cols-3`} onSubmit={async e => { e.preventDefault(); setBusy(true); try { await api(`/api/v1/admin/schedules${editing ? `/${editing}` : ""}`, { method: editing ? "PUT" : "POST", body: JSON.stringify(form) }); await load(); setEditing(""); setForm(initial); setMessage("Schedule saved."); } catch (err) { setMessage(errorText(err)); } finally { setBusy(false); } }}>
      <Field label="Schedule name"><input required className={control} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label="Route"><select required className={control} value={form.route_id} onChange={e => setForm({ ...form, route_id: e.target.value })}><option value="">Select route</option>{routes.map(r => <option key={r.id} value={r.id}>{r.route_name}</option>)}</select></Field>
      <Field label="Bus"><select required className={control} value={form.bus_id} onChange={e => setForm({ ...form, bus_id: e.target.value })}><option value="">Select bus</option>{buses.map(b => <option key={b.id} value={b.id}>{b.display_name}</option>)}</select></Field>
      <Field label="Departure (IST)"><input type="time" required className={control} value={form.departure_time} onChange={e => setForm({ ...form, departure_time: e.target.value })} /></Field>
      <Field label="Journey duration (minutes)"><input type="number" min={1} required className={control} value={form.duration_minutes} onChange={e => setForm({ ...form, duration_minutes: Number(e.target.value) })} /></Field>
      <Field label="Fare (₹)"><input type="number" min={1} step="0.01" required className={control} value={form.base_fare_paise / 100} onChange={e => setForm({ ...form, base_fare_paise: Math.round(Number(e.target.value) * 100) })} /></Field>
      <Field label="Booking closes before departure (minutes)"><input type="number" min={0} required className={control} value={form.booking_cutoff_minutes} onChange={e => setForm({ ...form, booking_cutoff_minutes: Number(e.target.value) })} /></Field>
      <fieldset className="md:col-span-2"><legend className="mb-2 text-sm font-medium">Departure days</legend><div className="flex flex-wrap gap-4">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, i) => <label key={day} className="text-sm"><input type="checkbox" checked={form.weekdays.includes(i)} onChange={e => setForm({ ...form, weekdays: e.target.checked ? [...form.weekdays, i] : form.weekdays.filter(d => d !== i) })} /> {day}</label>)}</div></fieldset>
      <label><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} /> Active</label><button className={button} disabled={busy || !form.weekdays.length}>{editing ? "Save changes" : "Add schedule"}</button>
    </form>
    <section className={panel}><h2 className="font-semibold">Generate dated departures</h2><div className="grid gap-3 md:grid-cols-3"><Field label="From date"><input type="date" required className={control} value={range.start_date} onChange={e => setRange({ ...range, start_date: e.target.value })} /></Field><Field label="Through date (up to 91 days)"><input type="date" required className={control} value={range.end_date} onChange={e => setRange({ ...range, end_date: e.target.value })} /></Field><label className="self-end py-2"><input type="checkbox" checked={range.publish} onChange={e => setRange({ ...range, publish: e.target.checked })} /> Publish departures</label></div>
      {!rows.length && <p>No schedules yet.</p>}{rows.map(row => <article key={row.id} className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><p><strong>{row.name}</strong> · {row.definition.departure_time} IST · {row.active ? "active" : "inactive"}</p><div className="flex gap-4"><button className="underline" onClick={() => { setEditing(row.id); setForm(row.definition); }}>Edit</button><button className={button} disabled={busy || !row.active || !range.start_date || !range.end_date} onClick={async () => { setBusy(true); try { const result = await api<{ created: number }>(`/api/v1/admin/schedules/${row.id}/generate`, { method: "POST", body: JSON.stringify(range) }); setMessage(`${result.created} departures created. Previously generated dates were skipped.`); } catch (err) { setMessage(errorText(err)); } finally { setBusy(false); } }}>Generate trips</button></div></article>)}
    </section>
  </div>;
}
