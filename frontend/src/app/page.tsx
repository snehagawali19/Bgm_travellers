import Image from "next/image";
import { SearchCard } from "@/components/SearchCard";
import { SiteShell } from "@/components/SiteShell";
import { Armchair, Clock3, Headset, MapPinned, ShieldCheck } from "lucide-react";

const faqs = [
  {
    q: "Which route is currently on sale?",
    a: "Launch service is Belgaum (Belagavi) ↔ Bengaluru only. Tickets appear only when an admin publishes a trip for a specific date and departure.",
  },
  {
    q: "Does the bus run every day?",
    a: "No. Availability is not assumed. Search results show only published trips for the date you select.",
  },
  {
    q: "When do I get a PNR?",
    a: "A PNR and e-ticket are issued only after payment is verified and seats are confirmed. Pending payments do not create a ticket.",
  },
  {
    q: "Can I cancel online?",
    a: "Yes, from My Bookings. Refund estimates follow the sample development policy until the operator publishes final commercial terms.",
  },
  {
    q: "Can I track the bus live?",
    a: "Yes. Use Track Bus, or the link on your e-ticket. Position comes from GPS pings when available, otherwise a live schedule estimate along the Belgaum–Bengaluru corridor.",
  },
];

export default function HomePage() {
  return (
    <SiteShell>
      <section className="relative bg-white">
        <div className="relative h-[250px] md:h-[300px] lg:h-[340px]">
          <Image
            src="/images/bgm-bus.jpg"
            alt="BGM Travels BharatBenz coach on the highway"
            fill
            priority
            className="object-cover object-[center_42%]"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-black/15" />
          <h1 className="absolute bottom-24 left-4 z-[1] text-3xl font-extrabold text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.55)] md:bottom-28 md:left-10 md:text-4xl">
            Book bus tickets online
          </h1>
        </div>
        <div className="relative z-10 mx-auto -mt-[4.25rem] max-w-[1100px] px-4 pb-8">
          <SearchCard variant="hero" />
        </div>
      </section>

      <section id="about" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-16">
        <h2 className="text-2xl font-semibold text-navy">Why travel with us</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Armchair, title: "Comfortable Travel", body: "Assigned seats on a known bus, not a mystery aggregator listing." },
            { icon: Clock3, title: "Easy Booking", body: "Search, pick a seat, pay, and receive a PNR only after confirmation." },
            { icon: ShieldCheck, title: "Reliable Service", body: "Trips are published by the operator. If a date is empty, there is no service that night." },
            { icon: MapPinned, title: "Live Tracking", body: "Follow the bus on the map from Track Bus, your ticket, or admin GPS/demo replay." },
          ].map((item) => (
            <article key={item.title} className="rounded-2xl border border-neutral-200 bg-white p-6">
              <item.icon className="text-teal" />
              <h3 className="mt-4 text-lg font-semibold text-navy">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-navy/70">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="bg-white py-16">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold text-navy">Our route</h2>
            <p className="mt-3 text-navy/70">Belgaum ↔ Bengaluru. Each direction is a separate route so fares, stops and trips can differ.</p>
            <div className="mt-6 rounded-2xl bg-brand/15 p-6">
              <p className="text-sm uppercase tracking-wide text-navy/50">Launch corridor</p>
              <p className="mt-2 text-3xl font-semibold text-navy">Belgaum ↔ Bengaluru</p>
              <p className="mt-3 text-sm text-navy/60">Overnight AC seater · about 8h 30m · boarding and dropping points configured per route.</p>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-navy">Travel information</h2>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-navy/70">
              <li>Arrive at the boarding point 20 minutes early. Seat numbers are printed on your ticket.</li>
              <li>Fares are calculated on the server in paise. The amount you pay is never taken from the browser.</li>
              <li>Track the bus from the Track Bus page. Live GPS overrides the schedule estimate when a ping is less than 10 minutes old.</li>
              <li>Customer records are retrieved with PNR + mobile, or the private link issued after checkout.</li>
            </ul>
            <div className="mt-6 flex items-start gap-3 rounded-2xl border border-teal/20 bg-teal/5 p-4 text-sm text-navy/80">
              <Headset className="mt-0.5 text-teal" size={18} />
              Support placeholder: +91 83100 00000 ·  support@bgmtravels.in
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-2xl font-semibold text-navy">Frequently asked questions</h2>
        <div className="mt-6 space-y-3">
          {faqs.map((faq) => (
            <details key={faq.q} className="rounded-2xl border border-neutral-200 bg-white p-5">
              <summary className="cursor-pointer font-medium text-navy">{faq.q}</summary>
              <p className="mt-3 text-sm leading-6 text-navy/70">{faq.a}</p>
            </details>
          ))}
        </div>
      </section>
    </SiteShell>
  );
}
