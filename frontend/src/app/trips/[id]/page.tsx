"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api, Seat, TripCard } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";

const STATUS_CLASS: Record<string, string> = {
  available: "bg-white hover:border-teal cursor-pointer",
  selected: "bg-brand text-black border-brand",
  held: "bg-amber-100 text-amber-800 cursor-not-allowed",
  booked: "bg-navy/20 text-navy/40 cursor-not-allowed",
  blocked: "bg-slate-200 text-slate-400 cursor-not-allowed",
};

export default function SeatPage() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const needed = Number(params.get("passengers") || "1");
  const [trip, setTrip] = useState<TripCard | null>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ trip: TripCard; seats: Seat[] }>(`/api/v1/trips/${id}`)
      .then((data) => {
        setTrip(data.trip);
        setSeats(data.seats);
      })
      .catch((err) => setError(err.message));
  }, [id]);

  const rows = useMemo(() => {
    const grouped = new Map<number, Seat[]>();
    seats.forEach((seat) => {
      grouped.set(seat.row_no, [...(grouped.get(seat.row_no) || []), seat]);
    });
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]);
  }, [seats]);

  function toggle(seat: Seat) {
    if (seat.status !== "available" && !selected.includes(seat.id)) return;
    setSelected((current) => {
      if (current.includes(seat.id)) return current.filter((id) => id !== seat.id);
      if (current.length >= needed) return current;
      return [...current, seat.id];
    });
  }

  async function continueCheckout() {
    setError("");
    if (selected.length !== needed) {
      setError(`Select exactly ${needed} seat${needed > 1 ? "s" : ""}.`);
      return;
    }
    setBusy(true);
    try {
      const hold = await api<{ hold_token: string; expires_at: string; fare_paise: number; seat_numbers: string[] }>(
        "/api/v1/holds",
        { method: "POST", body: JSON.stringify({ trip_id: id, seat_ids: selected }) },
      );
      sessionStorage.setItem(
        "bgm_hold",
        JSON.stringify({ ...hold, trip_id: id, seat_ids: selected, passengers: needed }),
      );
      router.push("/checkout");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not hold seats");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SiteShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        {trip ? (
          <div className="mb-6">
            <p className="text-sm text-teal">{trip.bus_name}</p>
            <h1 className="text-2xl font-semibold text-navy">
              {trip.origin_name} → {trip.destination_name}
            </h1>
            <p className="text-sm text-navy/60">
              {formatIST(trip.departure_datetime)} · {formatPaise(trip.base_fare_paise)} per seat
            </p>
          </div>
        ) : null}
        <div className="grid gap-6 md:grid-cols-[1fr_280px]">
          <section className="rounded-3xl border border-navy/10 bg-white p-6">
            <p className="mb-4 text-center text-xs uppercase tracking-wide text-navy/40">Driver</p>
            <div className="space-y-2">
              {rows.map(([row, rowSeats]) => (
                <div key={row} className="flex items-center justify-center gap-2">
                  {rowSeats
                    .sort((a, b) => a.col_no - b.col_no)
                    .map((seat, index) => (
                      <div key={seat.id} className="contents">
                        {index === 2 ? <span className="w-8" /> : null}
                        <button
                          type="button"
                          onClick={() => toggle(seat)}
                          className={`h-10 w-10 rounded-lg border text-xs font-semibold ${
                            selected.includes(seat.id) ? STATUS_CLASS.selected : STATUS_CLASS[seat.status] || STATUS_CLASS.available
                          }`}
                          disabled={!["available"].includes(seat.status) && !selected.includes(seat.id)}
                        >
                          {seat.seat_number}
                        </button>
                      </div>
                    ))}
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap gap-3 text-xs text-navy/60">
              <span>White: available</span>
              <span>Green: selected</span>
              <span>Amber: held</span>
              <span>Grey: booked/blocked</span>
            </div>
          </section>
          <aside className="rounded-3xl border border-navy/10 bg-white p-6">
            <h2 className="font-semibold text-navy">Selection</h2>
            <p className="mt-2 text-sm text-navy/60">Choose {needed} seat{needed > 1 ? "s" : ""}.</p>
            <p className="mt-4 text-sm">{selected.length} selected</p>
            <p className="mt-2 text-xl font-semibold">{trip ? formatPaise(trip.base_fare_paise * selected.length) : "—"}</p>
            {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
            <button
              onClick={continueCheckout}
              disabled={busy}
              className="mt-4 w-full rounded-lg bg-brand py-3 text-sm font-bold text-black disabled:opacity-60"
            >
              {busy ? "Holding seats…" : "Continue"}
            </button>
            <p className="mt-3 text-xs text-navy/50">Seats are held for 10 minutes. Availability is re-checked on the server.</p>
          </aside>
        </div>
      </div>
    </SiteShell>
  );
}
