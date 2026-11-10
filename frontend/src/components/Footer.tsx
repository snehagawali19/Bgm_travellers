import Link from "next/link";
import { Logo } from "./Header";

export function Footer() {
  return (
    <footer className="mt-16 bg-brand text-black">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-4">
        <div>
          <Logo />
          <p className="mt-4 text-sm text-black/70">
            A Belgaum-based operator running a comfortable overnight service to Bengaluru. Additional buses and cities
            can be added from the admin dashboard.
          </p>
        </div>
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide">Travel</h3>
          <ul className="mt-3 space-y-2 text-sm text-black/75">
            <li><Link href="/">Book tickets</Link></li>
            <li><Link href="/track">Track bus</Link></li>
            <li><Link href="/my-bookings">My bookings</Link></li>
            <li><Link href="/contact">Contact us</Link></li>
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide">Policies</h3>
          <ul className="mt-3 space-y-2 text-sm text-black/75">
            <li>Cancellation terms are shown at checkout and stored with each booking.</li>
            <li>Current refund windows are sample development terms, not final commercial policy.</li>
            <li>Payments: Razorpay Test Mode until production credentials are approved.</li>
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide">Contact</h3>
          <ul className="mt-3 space-y-2 text-sm text-black/75">
            <li>Phone: +91 83100 00000</li>
            <li>Email:  support@bgmtravels.in</li>
            <li>RPD Cross, Belagavi, Karnataka 590006</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-black/10 py-4 text-center text-xs text-black/60">
        © {new Date().getFullYear()} BGM Travels
      </div>
    </footer>
  );
}
