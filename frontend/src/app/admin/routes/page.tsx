"use client";

import { useEffect, useState } from "react";
import { api, City } from "@/lib/api";
import RouteStopsEditor from "@/components/RouteStopsEditor";

type RouteRow = {
  id: string;
  origin_city_id: string;
  destination_city_id: string;
  origin_name: string;
  destination_name: string;
  route_name: string;
  estimated_duration_minutes: number;
  active: boolean;
};

export default function RoutesPage() {
  const [cities, setCities] = useState<Array<City & { country?: string; active?: boolean }>>([]);
  const [routes, setRoutes] = useState<RouteRow[]>([]);
  const [editing, setEditing] = useState("");
  const [cityForm, setCityForm] = useState({ name: "", slug: "", state: "Karnataka", aliases: "" });
  const [routeForm, setRouteForm] = useState({ origin_city_id: "", destination_city_id: "", route_name: "", estimated_duration_minutes: 510 });

  async function load() {
    setCities(await api("/api/v1/admin/cities"));
    setRoutes(await api("/api/v1/admin/routes"));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Cities and routes</h1>
      <form
        className="mt-6 grid gap-3 rounded-2xl border border-navy/10 bg-white p-4 md:grid-cols-5"
        onSubmit={async (event) => {
          event.preventDefault();
          await api("/api/v1/admin/cities", {
            method: "POST",
            body: JSON.stringify({ ...cityForm, aliases: cityForm.aliases.split(",").map((item) => item.trim()).filter(Boolean) }),
          });
          setCityForm({ name: "", slug: "", state: "Karnataka", aliases: "" });
          load();
        }}
      >
        <input placeholder="City name" className="rounded-xl border px-3 py-2" value={cityForm.name} onChange={(e) => setCityForm({ ...cityForm, name: e.target.value })} />
        <input placeholder="slug" className="rounded-xl border px-3 py-2" value={cityForm.slug} onChange={(e) => setCityForm({ ...cityForm, slug: e.target.value })} />
        <input placeholder="state" className="rounded-xl border px-3 py-2" value={cityForm.state} onChange={(e) => setCityForm({ ...cityForm, state: e.target.value })} />
        <input placeholder="aliases, comma separated" className="rounded-xl border px-3 py-2" value={cityForm.aliases} onChange={(e) => setCityForm({ ...cityForm, aliases: e.target.value })} />
        <button className="rounded-lg bg-brand font-bold text-black">Add city</button>
      </form>

      <form
        className="mt-4 grid gap-3 rounded-2xl border border-navy/10 bg-white p-4 md:grid-cols-5"
        onSubmit={async (event) => {
          event.preventDefault();
          await api("/api/v1/admin/routes", { method: "POST", body: JSON.stringify(routeForm) });
          load();
        }}
      >
        <select className="rounded-xl border px-3 py-2" value={routeForm.origin_city_id} onChange={(e) => setRouteForm({ ...routeForm, origin_city_id: e.target.value })}>
          <option value="">Origin</option>
          {cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
        </select>
        <select className="rounded-xl border px-3 py-2" value={routeForm.destination_city_id} onChange={(e) => setRouteForm({ ...routeForm, destination_city_id: e.target.value })}>
          <option value="">Destination</option>
          {cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
        </select>
        <input placeholder="Route name" className="rounded-xl border px-3 py-2" value={routeForm.route_name} onChange={(e) => setRouteForm({ ...routeForm, route_name: e.target.value })} />
        <input type="number" className="rounded-xl border px-3 py-2" value={routeForm.estimated_duration_minutes} onChange={(e) => setRouteForm({ ...routeForm, estimated_duration_minutes: Number(e.target.value) })} />
        <button className="rounded-lg bg-brand font-bold text-black">Add route</button>
      </form>

      <div className="mt-6 space-y-2">
        {routes.map((route) => (
          <div key={route.id} className="rounded-2xl border border-navy/10 bg-white p-4 text-sm">
            {route.route_name} · {route.estimated_duration_minutes} min · {route.active ? "active" : "inactive"}
            <button className="ml-4 underline" onClick={() => setEditing(route.id)}>Configure stops</button>
          </div>
        ))}
      </div>
      {editing && <RouteStopsEditor routeId={editing} />}
    </div>
  );
}
