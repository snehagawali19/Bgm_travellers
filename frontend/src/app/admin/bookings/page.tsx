"use client";

import { useEffect, useState } from "react";
import { api, Booking } from "@/lib/api";
import { formatIST, formatPaise } from "@/lib/format";

export default function AdminBookingsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  useEffect(() => {
    api<Booking[]>("/api/v1/admin/bookings").then(setBookings);
  }, []);
  return (
    <div>
      <h1 className="text-2xl font-semibold text-navy">Bookings</h1>
      <div className="mt-6 overflow-x-auto rounded-2xl border border-navy/10 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-cream text-navy/60">
            <tr>
              <th className="px-4 py-3">PNR</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Trip</th>
              <th className="px-4 py-3">Amount</th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((booking) => (
              <tr key={booking.public_reference} className="border-t border-navy/10">
                <td className="px-4 py-3">{booking.pnr || "—"}</td>
                <td className="px-4 py-3">{booking.status}</td>
                <td className="px-4 py-3">{booking.customer_name}<br />{booking.customer_phone}</td>
                <td className="px-4 py-3">{booking.trip.route_name}<br />{formatIST(booking.trip.departure_datetime)}</td>
                <td className="px-4 py-3">{formatPaise(booking.total_amount_paise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
