"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import FleetEditor, { FleetBus } from "@/components/FleetEditor";

type Bus = {
  id: string;
  registration_number: string;
  display_name: string;
  bus_type: string;
  seat_capacity: number;
  status: string;
  amenities: string[];
};

export default function FleetPage() {
  const [buses, setBuses] = useState<Bus[]>([]);
  const [form, setForm] = useState({
    registration_number: "",
    display_name: "",
    bus_type: "seater",
    seat_capacity: 40,
    status: "active",
  });
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState("");

  function load() {
    api<Bus[]>("/api/v1/admin/buses").then(setBuses).catch(e => setMessage(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function createBus(event: React.FormEvent) {
    event.preventDefault();
    await api("/api/v1/admin/buses", { method: "POST", body: JSON.stringify({ ...form, amenities: ["ac"] }) });
    setMessage("Bus registered. Configure a unique seat layout before publishing trips.");
    load();
  }

  async function addDefaultLayout(bus: Bus) {
    const seats = [];
    const rows = Math.ceil(bus.seat_capacity / 4) || 10;
    const letters = ["A", "B", "C", "D"];
    const types = ["window", "aisle", "aisle", "window"];
    let count = 0;
    for (let row = 1; row <= rows; row += 1) {
      for (let col = 0; col < 4 && count < bus.seat_capacity; col += 1) {
        count += 1;
        seats.push({
          seat_number: `${row}${letters[col]}`,
          seat_type: types[col],
          row_no: row,
          col_no: col + 1,
          deck: "lower",
          active: true,
        });
      }
    }
    await api(`/api/v1/admin/buses/${bus.id}/seats`, { method: "PUT", body: JSON.stringify(seats) });
    setMessage(`Seat layout saved for ${bus.display_name}.`);
    load();
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Fleet</h1>
      <form onSubmit={createBus} className="mt-6 grid gap-3 rounded-2xl border border-navy/10 bg-white p-4 md:grid-cols-5">
        <input placeholder="KA-22-N-0000" className="rounded-xl border border-navy/10 px-3 py-2" value={form.registration_number} onChange={(e) => setForm({ ...form, registration_number: e.target.value })} />
        <input placeholder="Display name" className="rounded-xl border border-navy/10 px-3 py-2" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        <select className="rounded-xl border border-navy/10 px-3 py-2" value={form.bus_type} onChange={(e) => setForm({ ...form, bus_type: e.target.value })}>
          <option value="seater">Seater</option>
          <option value="sleeper">Sleeper</option>
          <option value="semi_sleeper">Semi sleeper</option>
        </select>
        <input type="number" className="rounded-xl border border-navy/10 px-3 py-2" value={form.seat_capacity} onChange={(e) => setForm({ ...form, seat_capacity: Number(e.target.value) })} />
        <button className="rounded-lg bg-brand font-bold text-black">Add bus</button>
      </form>
      {message ? <p className="mt-3 text-sm text-teal">{message}</p> : null}
      <div className="mt-6 space-y-3">
        {buses.map((bus) => (
          <article key={bus.id} className="flex flex-wrap items-center justify-between rounded-2xl border border-navy/10 bg-white p-4">
            <div>
              <p className="font-semibold text-navy">{bus.display_name}</p>
              <p className="text-sm text-navy/60">{bus.registration_number} · {bus.bus_type} · {bus.seat_capacity} seats · {bus.status}</p>
            </div>
            <div className="flex gap-4"><button onClick={() => setEditing(bus.id)} className="text-sm underline">Edit bus and layout</button><button onClick={() => addDefaultLayout(bus).catch(e => setMessage(e.message))} className="text-sm text-teal">Apply 2+2 layout</button></div>
          </article>
        ))}
      </div>
      {editing && buses.some(b => b.id === editing) && <FleetEditor bus={buses.find(b => b.id === editing) as FleetBus} onSaved={load} />}
    </div>
  );
}
