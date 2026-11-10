"use client";

import { ArrowLeftRight, CalendarDays, ChevronLeft, ChevronRight, MapPin, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, City } from "@/lib/api";
import { departureLabel, shiftISO, todayISO } from "@/lib/format";

type Props = {
  compact?: boolean;
  variant?: "card" | "hero";
  initial?: {
    origin?: string;
    destination?: string;
    date?: string;
    passengers?: string;
  };
};

const fieldClass =
  "h-11 w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm text-black outline-none focus:border-black";

export function SearchCard({ compact = false, variant = "card", initial }: Props) {
  const router = useRouter();
  const hero = variant === "hero";
  const [cities, setCities] = useState<City[]>([]);
  const [origin, setOrigin] = useState(initial?.origin || "");
  const [destination, setDestination] = useState(initial?.destination || "");
  const [date, setDate] = useState(initial?.date || todayISO());
  const [passengers, setPassengers] = useState(initial?.passengers || "1");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<City[]>("/api/v1/cities")
      .then((data) => {
        setCities(data);
        if (!initial?.origin) {
          const belgaum = data.find((city) => city.slug === "belgaum");
          const bengaluru = data.find((city) => city.slug === "bengaluru");
          if (belgaum) setOrigin(belgaum.id);
          if (bengaluru) setDestination(bengaluru.id);
        }
      })
      .catch(() => setError("Could not load cities. Start the API and seed data first."))
      .finally(() => setLoading(false));
  }, [initial?.origin]);

  const minDate = todayISO();
  const originCity = useMemo(() => cities.find((city) => city.id === origin), [cities, origin]);

  function swap() {
    setOrigin(destination);
    setDestination(origin);
  }

  function stepDate(days: number) {
    const next = shiftISO(date, days);
    if (next < minDate) return;
    setDate(next);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!origin || !destination) return setError("Choose origin and destination.");
    if (origin === destination) return setError("Origin and destination must be different.");
    if (!date) return setError("Choose a travel date.");
    if (date < minDate) return setError("Travel date cannot be in the past.");
    const params = new URLSearchParams({ origin, destination, date, passengers });
    router.push(`/search?${params.toString()}`);
  }

  return (
    <form
      onSubmit={submit}
      className={`rounded-2xl bg-white ${
        hero
          ? "p-5 shadow-[0_12px_40px_rgba(0,0,0,0.18)] md:p-6"
          : `border border-navy/10 shadow-[0_10px_30px_rgba(11,31,58,0.08)] ${compact ? "p-4" : "p-5 md:p-6"}`
      }`}
    >
      <div className="mb-4 flex items-center gap-5 text-sm font-medium text-black">
        <label className="flex cursor-pointer items-center gap-2">
          <input type="radio" name="trip-type" checked onChange={() => undefined} className="accent-black" />
          One Way
        </label>
        <span className="flex items-center gap-2 text-black/35" title="Round trip is not available yet">
          <input type="radio" name="trip-type" disabled className="accent-black" />
          Round Trip
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_1.15fr_0.95fr_auto] md:items-end">
        <label className="block">
          <span className="mb-1 block text-xs text-neutral-500">From</span>
          <span className="relative block">
            <MapPin size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-neutral-500" />
            <select
              className={`${fieldClass} pl-9`}
              value={origin}
              onChange={(event) => setOrigin(event.target.value)}
              disabled={loading}
              aria-label="From"
            >
              <option value="">Select city</option>
              {cities.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name}
                </option>
              ))}
            </select>
          </span>
        </label>
        <button
          type="button"
          onClick={swap}
          className="mx-auto flex h-9 w-9 items-center justify-center rounded-full border border-neutral-300 bg-white text-neutral-700 hover:border-black md:mb-1"
          aria-label="Swap origin and destination"
        >
          <ArrowLeftRight size={16} />
        </button>
        <label className="block">
          <span className="mb-1 block text-xs text-neutral-500">To</span>
          <span className="relative block">
            <MapPin size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-neutral-500" />
            <select
              className={`${fieldClass} pl-9`}
              value={destination}
              onChange={(event) => setDestination(event.target.value)}
              disabled={loading}
              aria-label="To"
            >
              <option value="">Select city</option>
              {cities.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name}
                </option>
              ))}
            </select>
          </span>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-neutral-500">Departure</span>
          <div className="relative flex h-11 items-center rounded-lg border border-neutral-300 bg-white pr-1">
            <CalendarDays size={16} className="ml-3 shrink-0 text-neutral-500" />
            <span className="min-w-0 flex-1 truncate px-2 text-sm">{departureLabel(date)}</span>
            <input
              type="date"
              min={minDate}
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="absolute inset-y-0 left-0 right-16 cursor-pointer opacity-0"
              aria-label="Travel date"
            />
            <button
              type="button"
              onClick={() => stepDate(-1)}
              disabled={date <= minDate}
              className="relative z-10 flex h-8 w-7 items-center justify-center rounded text-neutral-600 hover:bg-neutral-100 disabled:opacity-30"
              aria-label="Previous day"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              type="button"
              onClick={() => stepDate(1)}
              className="relative z-10 flex h-8 w-7 items-center justify-center rounded text-neutral-600 hover:bg-neutral-100"
              aria-label="Next day"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-neutral-500">Passengers</span>
          <span className="relative block">
            <Users size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-neutral-500" />
            <select
              className={`${fieldClass} pl-9`}
              value={passengers}
              onChange={(event) => setPassengers(event.target.value)}
              aria-label="Passengers"
            >
              {[1, 2, 3, 4, 5, 6].map((count) => (
                <option key={count} value={count}>
                  {count} {count === 1 ? "Adult" : "Adults"}
                </option>
              ))}
            </select>
          </span>
        </label>
        <button
          type="submit"
          className="h-11 rounded-lg bg-brand px-7 text-sm font-bold text-black hover:bg-brand-dark"
        >
          Search
        </button>
      </div>
      {!hero && originCity ? (
        <p className="mt-3 text-xs text-navy/50">
          Showing only cities with published routes. {originCity.name} aliases: {originCity.aliases.join(", ") || "none"}.
        </p>
      ) : null}
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
    </form>
  );
}
