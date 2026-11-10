"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatPaise } from "@/lib/format";

type Order = {
  id: string;
  gateway_order_id: string;
  amount_paise: number;
  status: string;
  booking_reference: string;
  channel: string;
  transactions: Array<{ gateway_payment_id: string; status: string; amount_paise: number }>;
};

type Refund = { id: string; amount_paise: number; status: string; gateway_refund_id: string | null; channel: string; booking_reference: string };

export default function PaymentsPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    setOrders(await api("/api/v1/admin/payments"));
    setRefunds(await api("/api/v1/admin/refunds"));
  }

  useEffect(() => {
    load().catch(e => setMessage(e.message));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Payments and refunds</h1>
      {message && <p role="status" className="my-4 text-sm text-red-700">{message}</p>}
      <div className="mt-6 space-y-3">
        {orders.map((order) => (
          <article key={order.id} className="rounded-2xl border border-navy/10 bg-white p-4 text-sm">
            <p className="font-medium">{order.gateway_order_id} · {order.status} · {formatPaise(order.amount_paise)}</p>
            <p>{order.booking_reference} · {order.channel}</p>
            {order.channel === "online" && <button className="mt-2 underline" onClick={async () => { try { await api(`/api/v1/admin/bookings/${order.booking_reference}/reconcile`, { method: "POST" }); await load(); setMessage("Gateway status reconciled."); } catch (e) { setMessage(e instanceof Error ? e.message : "Reconciliation failed"); } }}>Reconcile with gateway</button>}
            {order.transactions.map((txn) => (
              <p key={txn.gateway_payment_id} className="text-navy/60">{txn.gateway_payment_id} · {txn.status}</p>
            ))}
          </article>
        ))}
      </div>
      <h2 className="mt-8 text-lg font-semibold text-navy">Refunds</h2>
      <div className="mt-3 space-y-3">
        {refunds.map((refund) => (
          <article key={refund.id} className="flex items-center justify-between rounded-2xl border border-navy/10 bg-white p-4 text-sm">
            <p>{formatPaise(refund.amount_paise)} · {refund.status} · {refund.gateway_refund_id || "no gateway id yet"}</p>
            {refund.status !== "processed" ? (
              <button className="text-teal" onClick={async () => { try { if (refund.channel !== "online") { const reference = window.prompt("Enter the receipt/reference after returning this refund to the customer:"); if (!reference) return; await api(`/api/v1/admin/refunds/${refund.id}/record-offline`, { method: "POST", body: JSON.stringify({ reference }) }); } else { await api(`/api/v1/admin/refunds/${refund.id}/retry`, { method: "POST" }); } await load(); } catch (e) { setMessage(e instanceof Error ? e.message : "Refund update failed"); } }}>{refund.channel === "online" ? "Retry / reconcile" : "Record money returned"}</button>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
