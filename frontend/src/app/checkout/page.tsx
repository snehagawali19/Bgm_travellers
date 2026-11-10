"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api, Booking, Customer, TripCard } from "@/lib/api";
import { formatPaise } from "@/lib/format";

type HoldState = {
  hold_token: string;
  trip_id: string;
  seat_ids: string[];
  seat_numbers: string[];
  fare_paise: number;
  expires_at: string;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export default function CheckoutPage() {
  const router = useRouter();
  const [hold, setHold] = useState<HoldState | null>(null);
  const [trip, setTrip] = useState<TripCard | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [passengers, setPassengers] = useState<Array<{ name: string; age: string; gender: string }>>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingBooking, setPendingBooking] = useState<Booking | null>(null);
  const [policyText, setPolicyText] = useState("");

  useEffect(() => {
    const raw = sessionStorage.getItem("bgm_hold");
    if (!raw) return;
    const parsed = JSON.parse(raw) as HoldState;
    setHold(parsed);
    setPassengers(parsed.seat_ids.map(() => ({ name: "", age: "", gender: "male" })));
    api<{ trip: TripCard; cancellation_disclaimer: string | null }>(`/api/v1/trips/${parsed.trip_id}`).then((data) => {
      setTrip(data.trip);
      setPickup(data.trip.pickup_stops[0]?.id || "");
      setDropoff(data.trip.dropoff_stops[0]?.id || "");
      setPolicyText(data.cancellation_disclaimer || "Contact the agency for cancellation terms.");
    }).catch(e => setError(e.message));
    api<Customer>("/api/v1/auth/me")
      .then((user) => {
        setName((current) => current || user.name);
        setEmail((current) => current || user.email);
        setPhone((current) => current || user.phone);
      })
      .catch(() => undefined);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    document.body.appendChild(script);
  }, []);

  async function pay(booking: Booking) {
    const payment = booking.payment;
    if (!payment) throw new Error("Payment order missing");
    const redirect = `/bookings/${booking.public_reference}?access_token=${booking.access_token}`;
    if (payment.provider === "fake") {
      const verified = await api<Booking>("/api/v1/payments/verify", {
        method: "POST",
        body: JSON.stringify({
          public_reference: booking.public_reference,
          gateway_order_id: payment.order_id,
          gateway_payment_id: `pay_ok_${Date.now()}`,
          gateway_signature: "test_signature",
        }),
      });
      router.push(`/bookings/${verified.public_reference}?access_token=${verified.access_token}`);
      return;
    }
    if (!window.Razorpay || !payment.key_id) throw new Error("Razorpay checkout is not available");
    const checkout = new window.Razorpay({
      key: payment.key_id,
      amount: payment.amount_paise,
      currency: payment.currency,
      name: "BGM Travels",
      order_id: payment.order_id,
      handler: async (response: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => {
        try { const verified = await api<Booking>("/api/v1/payments/verify", {
          method: "POST",
          body: JSON.stringify({
            public_reference: booking.public_reference,
            gateway_order_id: response.razorpay_order_id,
            gateway_payment_id: response.razorpay_payment_id,
            gateway_signature: response.razorpay_signature,
          }),
        });
        router.push(`/bookings/${verified.public_reference}?access_token=${verified.access_token}`);
        } catch { router.push(redirect); }
      },
      modal: { ondismiss: () => router.push(redirect) },
    });
    checkout.open();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!hold || !trip) return;
    setBusy(true);
    setError("");
    try {
      const booking = pendingBooking || await api<Booking>("/api/v1/bookings", {
        method: "POST",
        body: JSON.stringify({
          hold_token: hold.hold_token,
          customer_name: name,
          customer_email: email,
          customer_phone: phone,
          pickup_stop_id: pickup,
          dropoff_stop_id: dropoff,
          passengers: hold.seat_ids.map((seatId, index) => ({
            name: passengers[index].name,
            age: Number(passengers[index].age),
            gender: passengers[index].gender,
            seat_id: seatId,
          })),
        }),
      });
      setPendingBooking(booking);
      await pay(booking);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  if (!hold) {
    return (
      <SiteShell>
        <div className="mx-auto max-w-xl px-4 py-16 text-center">
          <p className="text-navy">No active seat hold. Search for a trip and select seats first.</p>
        </div>
      </SiteShell>
    );
  }

  return (
    <SiteShell>
      <form onSubmit={submit} className="mx-auto grid max-w-6xl gap-6 px-4 py-8 md:grid-cols-[1fr_320px]">
        <section className="rounded-3xl border border-navy/10 bg-white p-6">
          <h1 className="text-2xl font-semibold text-navy">Passenger details</h1>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <input required placeholder="Contact name" className="rounded-lg border border-neutral-300 bg-white px-3 py-3" value={name} onChange={(e) => setName(e.target.value)} />
            <input required type="email" placeholder="Email" className="rounded-lg border border-neutral-300 bg-white px-3 py-3" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input required placeholder="10-digit mobile" className="rounded-lg border border-neutral-300 bg-white px-3 py-3" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <select className="rounded-lg border border-neutral-300 bg-white px-3 py-3" value={pickup} onChange={(e) => setPickup(e.target.value)}>
              {trip?.pickup_stops.map((stop) => (
                <option key={stop.id} value={stop.id}>{stop.stop_name}</option>
              ))}
            </select>
            <select className="rounded-lg border border-neutral-300 bg-white px-3 py-3" value={dropoff} onChange={(e) => setDropoff(e.target.value)}>
              {trip?.dropoff_stops.map((stop) => (
                <option key={stop.id} value={stop.id}>{stop.stop_name}</option>
              ))}
            </select>
          </div>
          <div className="mt-6 space-y-4">
            {hold.seat_numbers.map((seat, index) => (
              <div key={seat} className="grid gap-3 rounded-2xl bg-sand p-4 md:grid-cols-4">
                <p className="font-medium text-navy">Seat {seat}</p>
                <input required placeholder="Passenger name" className="rounded-xl border border-navy/10 px-3 py-2" value={passengers[index]?.name || ""} onChange={(e) => setPassengers((rows) => rows.map((row, i) => i === index ? { ...row, name: e.target.value } : row))} />
                <input required type="number" min={1} max={120} placeholder="Age" className="rounded-xl border border-navy/10 px-3 py-2" value={passengers[index]?.age || ""} onChange={(e) => setPassengers((rows) => rows.map((row, i) => i === index ? { ...row, age: e.target.value } : row))} />
                <select className="rounded-xl border border-navy/10 px-3 py-2" value={passengers[index]?.gender || "male"} onChange={(e) => setPassengers((rows) => rows.map((row, i) => i === index ? { ...row, gender: e.target.value } : row))}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
            ))}
          </div>
        </section>
        <aside className="rounded-3xl border border-navy/10 bg-white p-6">
          <h2 className="font-semibold text-navy">Fare</h2>
          <p className="mt-2 text-sm text-navy/60">{hold.seat_numbers.length} seat(s)</p>
          <p className="mt-2 text-3xl font-semibold">{formatPaise(hold.fare_paise)}</p>
          <p className="mt-4 text-xs leading-5 text-navy/50">
            {policyText}
          </p>
          {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
          <button disabled={busy} className="mt-4 w-full rounded-lg bg-brand py-3 font-bold text-black">
            {busy ? "Processing…" : "Pay and confirm"}
          </button>
        </aside>
      </form>
    </SiteShell>
  );
}
