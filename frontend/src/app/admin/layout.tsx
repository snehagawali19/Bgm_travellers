"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const links = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/fleet", label: "Fleet" },
  { href: "/admin/routes", label: "Routes" },
  { href: "/admin/trips", label: "Trips" },
  { href: "/admin/tracking", label: "Tracking" },
  { href: "/admin/bookings", label: "Bookings" },
  { href: "/admin/payments", label: "Payments" },
  { href: "/admin/counter", label: "Counter / phone" },
  { href: "/admin/schedules", label: "Schedules" },
  { href: "/admin/reports", label: "Reports" },
  { href: "/admin/settings", label: "Staff and notifications" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/admin/login";
  const [role, setRole] = useState("booking_staff");
  const visibleLinks = role === "booking_staff" ? links.filter(l => ["/admin", "/admin/trips", "/admin/bookings", "/admin/counter", "/admin/tracking"].includes(l.href)) : links;

  useEffect(() => {
    if (isLogin) return;
    api<{ role: string }>("/api/v1/admin/auth/me").then(user => setRole(user.role)).catch(() => router.push("/admin/login"));
  }, [isLogin, router]);

  if (isLogin) return children;

  return (
    <div className="min-h-screen bg-white">
      <aside className="fixed inset-y-0 left-0 hidden w-56 border-r border-neutral-200 bg-white p-4 md:block">
        <p className="font-display text-lg font-bold text-brand">BGM TRAVELS</p>
        <p className="text-xs font-semibold text-black/60">Admin</p>
        <nav className="mt-6 flex flex-col gap-2 text-sm">
          {visibleLinks.map((link) => (
            <Link key={link.href} href={link.href} className={`rounded-lg px-3 py-2 font-semibold ${pathname === link.href ? "bg-brand text-black" : "text-black/70 hover:bg-sand"}`}>
              {link.label}
            </Link>
          ))}
        </nav>
        <button
          className="mt-8 text-sm font-semibold text-black/60"
          onClick={() => api("/api/v1/admin/auth/logout", { method: "POST" }).finally(() => router.push("/admin/login"))}
        >
          Log out
        </button>
      </aside>
      <div className="md:pl-56">
        <div className="flex gap-3 overflow-x-auto border-b border-neutral-200 bg-brand p-3 md:hidden">
          {visibleLinks.map((link) => (
            <Link key={link.href} href={link.href} className="whitespace-nowrap text-sm font-semibold text-black">{link.label}</Link>
          ))}
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}
