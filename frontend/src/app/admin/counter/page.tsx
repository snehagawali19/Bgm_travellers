"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Booking, Seat, TripCard } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";
import { Field, Notice, control, button, panel, errorText } from "@/components/AdminControls";

type Passenger = { seat_id: string; name: string; age: number; gender: string };

export default function CounterPage() {
  const [trips, setTrips] = useState<TripCard[]>([]);
  const [tripId, setTripId] = useState("");
  const [seats, setSeats] = useState<Seat[]>([]);
  const [passengers, setPassengers] = useState<Passenger[]>([]);
  const [details, setDetails] = useState({ customer_name: "", customer_phone: "", customer_email: "", pickup_stop_id: "", dropoff_stop_id: "", channel: "counter", payment_method: "cash", payment_reference: "" });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [booking, setBooking] = useState<Booking | null>(null);
  const trip = trips.find(t => t.id === tripId);
  useEffect(() => { api<TripCard[]>("/api/v1/admin/trips").then(rows => setTrips(rows.filter(t => t.status === "published"))).catch(e => setMessage(errorText(e))); setRequestId(crypto.randomUUID()); }, []);
  useEffect(() => {
    let current = true;
    setPassengers([]); setSeats([]); setBooking(null);
    setDetails(d => ({ ...d, pickup_stop_id: "", dropoff_stop_id: "" }));
    if (tripId) api<Seat[]>(`/api/v1/admin/trips/${tripId}/inventory`).then(rows => { if (current) setSeats(rows); }).catch(e => setMessage(errorText(e)));
    return () => { current = false; };
  }, [tripId]);
  function updatePassenger(index: number, values: Partial<Passenger>) { setPassengers(rows => rows.map((p, i) => i === index ? { ...p, ...values } : p)); }

  return <div className="max-w-5xl space-y-5">
    <h1 className="text-2xl font-semibold">Counter and phone booking</h1>
    <p className="text-sm text-neutral-600">Select available seats, enter passengers, and confirm only after collecting the offline payment.</p>
    <Notice message={message} />
    {booking ? <section className={panel}><h2 className="text-xl font-bold">Confirmed: {booking.pnr}</h2><p>{formatPaise(booking.total_amount_paise)} · {booking.seats.map(s => s.seat_number).join(", ")}</p><Link className={button} href={`/bookings/${booking.public_reference}?access_token=${booking.access_token}`}>Open ticket</Link><button className="ml-4 underline" onClick={() => { setBooking(null); setPassengers([]); setRequestId(crypto.randomUUID()); setTripId(""); }}>New booking</button></section> : <form className="space-y-5" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setMessage("");
      try { const result = await api<Booking>("/api/v1/admin/counter-bookings", { method: "POST", body: JSON.stringify({ ...details, trip_id: tripId, passengers, request_id: requestId }) }); setBooking(result); }
      catch (err) { setMessage(errorText(err)); if (tripId) setSeats(await api<Seat[]>(`/api/v1/admin/trips/${tripId}/inventory`).catch(() => seats)); }
      finally { setBusy(false); }
    }}>
      <Field label="Departure"><select required className={control} value={tripId} onChange={e => { setTripId(e.target.value); setRequestId(crypto.randomUUID()); }}><option value="">Choose a departure</option>{trips.map(t => <option key={t.id} value={t.id}>{t.route_name} · {formatIST(t.departure_datetime)} · {t.bus_name}</option>)}</select></Field>
      {trip && <>
        <section className={panel}><h2 className="font-semibold">Seats · {formatPaise(trip.base_fare_paise)} each</h2><div className="flex flex-wrap gap-2">{seats.map(s => <button type="button" key={s.id} disabled={s.status !== "available" || (passengers.length >= 10 && !passengers.some(p => p.seat_id === s.id))} aria-pressed={passengers.some(p => p.seat_id === s.id)} className={`rounded border px-4 py-3 disabled:opacity-30 ${passengers.some(p => p.seat_id === s.id) ? "bg-brand" : "bg-white"}`} onClick={() => setPassengers(rows => rows.some(p => p.seat_id === s.id) ? rows.filter(p => p.seat_id !== s.id) : [...rows, { seat_id: s.id, name: "", age: 30, gender: "male" }])}>{s.seat_number}<span className="block text-xs">{s.status}</span></button>)}</div></section>
        <section className={panel}><h2 className="font-semibold">Passenger details</h2>{passengers.map((p, i) => <div className="grid gap-3 md:grid-cols-4" key={p.seat_id}><p className="self-center font-medium">Seat {seats.find(s => s.id === p.seat_id)?.seat_number}</p><Field label="Name"><input required minLength={2} className={control} value={p.name} onChange={e => updatePassenger(i, { name: e.target.value })} /></Field><Field label="Age"><input required type="number" min={1} max={120} className={control} value={p.age} onChange={e => updatePassenger(i, { age: Number(e.target.value) })} /></Field><Field label="Gender"><select className={control} value={p.gender} onChange={e => updatePassenger(i, { gender: e.target.value })}><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select></Field></div>)}</section>
        <section className={`${panel} grid gap-4 md:grid-cols-3`}>
          <Field label="Contact name"><input required minLength={2} className={control} value={details.customer_name} onChange={e => setDetails({ ...details, customer_name: e.target.value })} /></Field>
          <Field label="Mobile"><input required type="tel" className={control} value={details.customer_phone} onChange={e => setDetails({ ...details, customer_phone: e.target.value })} /></Field>
          <Field label="Email"><input required type="email" className={control} value={details.customer_email} onChange={e => setDetails({ ...details, customer_email: e.target.value })} /></Field>
          <Field label="Boarding point"><select required className={control} value={details.pickup_stop_id} onChange={e => setDetails({ ...details, pickup_stop_id: e.target.value })}><option value="">Select pickup</option>{trip.pickup_stops.map(s => <option key={s.id} value={s.id}>{s.stop_name}</option>)}</select></Field>
          <Field label="Drop-off point"><select required className={control} value={details.dropoff_stop_id} onChange={e => setDetails({ ...details, dropoff_stop_id: e.target.value })}><option value="">Select drop-off</option>{trip.dropoff_stops.map(s => <option key={s.id} value={s.id}>{s.stop_name}</option>)}</select></Field>
          <Field label="Booking channel"><select className={control} value={details.channel} onChange={e => setDetails({ ...details, channel: e.target.value })}><option value="counter">Walk-in counter</option><option value="phone">Phone</option></select></Field>
          <Field label="Payment collected via"><select className={control} value={details.payment_method} onChange={e => setDetails({ ...details, payment_method: e.target.value })}><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option></select></Field>
          <Field label="Receipt / payment reference"><input required={details.payment_method !== "cash"} className={control} value={details.payment_reference} onChange={e => setDetails({ ...details, payment_reference: e.target.value })} /></Field>
        </section>
        <p className="font-semibold">Total: {formatPaise(passengers.length * trip.base_fare_paise)}</p>
        <button className={button} disabled={busy || !passengers.length}>{busy ? "Confirming…" : "Payment collected — confirm booking"}</button>
      </>}
    </form>}
  </div>;
}
