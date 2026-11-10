"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";
import { Notice, panel, errorText } from "@/components/AdminControls";

type Report = { gross_collections_paise: Record<string, number>; refunded_paise: number; pending_refunds_paise: number; pending_refunds_count: number; trips: { id: string; route_name: string; departure_datetime: string; total: number; available: number; held: number; booked: number; blocked: number; occupancy_percent: number }[] };
export default function ReportsPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => { api<Report>("/api/v1/admin/reports").then(setReport).catch(e => setMessage(errorText(e))); }, []);
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Collections and occupancy</h1><Notice message={message} />{report && <><div className="grid gap-4 md:grid-cols-3">{Object.entries(report.gross_collections_paise).map(([channel, amount]) => <article className={panel} key={channel}><p className="capitalize">{channel} gross collections</p><p className="text-2xl font-semibold">{formatPaise(amount)}</p></article>)}</div><div className="grid gap-4 md:grid-cols-3"><article className={panel}><p>Refunded</p><p className="text-2xl font-semibold">{formatPaise(report.refunded_paise)}</p></article><article className={panel}><p>Pending refunds · {report.pending_refunds_count}</p><p className="text-2xl font-semibold">{formatPaise(report.pending_refunds_paise)}</p></article><article className={panel}><p>Net collected after completed refunds</p><p className="text-2xl font-semibold">{formatPaise(Object.values(report.gross_collections_paise).reduce((a, b) => a + b, 0) - report.refunded_paise)}</p></article></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Departure", "Booked / total", "Held", "Blocked", "Available", "Occupancy"].map(h => <th className="border-b p-3" key={h}>{h}</th>)}</tr></thead><tbody>{report.trips.map(t => <tr key={t.id}><td className="border-b p-3">{t.route_name}<span className="block text-neutral-500">{formatIST(t.departure_datetime)}</span></td><td className="border-b p-3">{t.booked} / {t.total}</td><td className="border-b p-3">{t.held}</td><td className="border-b p-3">{t.blocked}</td><td className="border-b p-3">{t.available}</td><td className="border-b p-3">{t.occupancy_percent}%</td></tr>)}</tbody></table></div></>}</div>;
}
