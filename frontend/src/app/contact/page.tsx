import { SiteShell } from "@/components/SiteShell";

export default function ContactPage() {
  return (
    <SiteShell>
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-semibold text-navy">Contact us</h1>
        <p className="mt-3 text-navy/70">Placeholder operator contacts until live numbers are confirmed.</p>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <article className="rounded-2xl border border-neutral-200 bg-white p-6">
            <h2 className="font-semibold text-navy">Customer support</h2>
            <p className="mt-2 text-sm text-navy/70">+91 83100 00000</p>
            <p className="text-sm text-navy/70">support@bgmtravels.in</p>
          </article>
          <article className="rounded-2xl border border-neutral-200 bg-white p-6">
            <h2 className="font-semibold text-navy">Office</h2>
            <p className="mt-2 text-sm text-navy/70">RPD Cross, Belagavi, Karnataka 590006</p>
            <p className="text-sm text-navy/70">Hours: 09:00–21:00 IST</p>
          </article>
        </div>
      </div>
    </SiteShell>
  );
}
