"use client";
import { useState } from "react";
import { api, Booking } from "@/lib/api";

export default function RetryPayment({ booking, access, onUpdated }: { booking: Booking; access: string; onUpdated: (booking: Booking) => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function retry() {
    setBusy(true); setMessage("");
    try {
      const updated = await api<Booking>(`/api/v1/bookings/${booking.public_reference}/retry-payment?access_token=${access}`, { method: "POST" });
      const payment = updated.payment;
      if (!payment) throw new Error("Payment is no longer pending. Refresh your ticket.");
      async function verify(orderId: string, paymentId: string, signature: string) {
        try { onUpdated(await api<Booking>("/api/v1/payments/verify", { method: "POST", body: JSON.stringify({ public_reference: booking.public_reference, gateway_order_id: orderId, gateway_payment_id: paymentId, gateway_signature: signature }) })); }
        catch (e) { setMessage(e instanceof Error ? e.message : "Verification pending. Please refresh shortly."); }
        finally { setBusy(false); }
      }
      if (payment.provider === "fake") { await verify(payment.order_id, `pay_ok_${crypto.randomUUID()}`, "test_signature"); return; }
      if (!window.Razorpay) await new Promise<void>((resolve, reject) => { const script = document.createElement("script"); script.src = "https://checkout.razorpay.com/v1/checkout.js"; script.onload = () => resolve(); script.onerror = () => reject(new Error("Could not load payment checkout")); document.body.appendChild(script); });
      if (!window.Razorpay) throw new Error("Payment checkout is unavailable");
      new window.Razorpay({ key: payment.key_id, order_id: payment.order_id, amount: payment.amount_paise, currency: payment.currency, name: "BGM Travels", handler: (response: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => verify(response.razorpay_order_id, response.razorpay_payment_id, response.razorpay_signature), modal: { ondismiss: () => setBusy(false) } }).open();
    } catch (e) { setMessage(e instanceof Error ? e.message : "Payment could not be retried"); setBusy(false); }
  }
  return <div><button disabled={busy} onClick={retry} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold disabled:opacity-50">{busy ? "Opening payment…" : "Retry payment"}</button>{message && <p role="status" className="mt-2 text-sm text-red-700">{message}</p>}</div>;
}
