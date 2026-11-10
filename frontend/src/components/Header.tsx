"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CircleUser, Menu, Phone, X } from "lucide-react";
import { api } from "@/lib/api";

type Customer = { id: string; name: string; email: string; phone: string };

export function Logo() {
  return (
    <Link href="/" className="shrink-0 font-display text-[1.45rem] font-bold tracking-wide text-white lg:text-[1.65rem]">
      BGM TRAVELS
    </Link>
  );
}

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const links = [
    { href: "/", label: "Plan Your Journey" },
    { href: "/track", label: "Trip Tracker" },
    { href: "/my-bookings", label: "My Bookings" },
    { href: "/contact", label: "Help" },
  ];

  useEffect(() => {
    api<Customer>("/api/v1/auth/me")
      .then(setCustomer)
      .catch(() => setCustomer(null));
  }, [pathname]);

  async function signOut() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch {
      /* already signed out */
    }
    setCustomer(null);
    setOpen(false);
    router.push("/");
    router.refresh();
  }

  const account = customer ? (
    <>
      <span className="max-w-[9rem] truncate">{customer.name}</span>
      <button type="button" onClick={signOut} className="hover:opacity-70">
        Sign out
      </button>
    </>
  ) : (
    <>
      <Link href="/login" className="flex items-center gap-1.5 hover:opacity-70">
        <CircleUser size={18} />
        Sign in
      </Link>
      <Link href="/login?as=operator" className="hover:opacity-70">
        Operator
      </Link>
    </>
  );

  return (
    <header className="sticky top-0 z-40 bg-brand">
      <div className="flex w-full items-center gap-6 px-4 py-2.5 lg:px-6">
        <Logo />
        <nav className="ml-auto hidden items-center gap-5 text-[13px] font-semibold text-black whitespace-nowrap lg:flex">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="hover:opacity-70">
              {link.label}
            </Link>
          ))}
          <a href="tel:+918310000000" className="flex items-center gap-1.5 hover:opacity-70">
            <Phone size={15} />
            Call to book 83100 00000
          </a>
          {account}
        </nav>
        <button className="text-black lg:hidden" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
          {open ? <X /> : <Menu />}
        </button>
      </div>
      {open ? (
        <div className="border-t border-black/10 bg-brand px-4 py-4 lg:hidden">
          <div className="flex flex-col gap-3 text-sm font-semibold text-black">
            {links.map((link) => (
              <Link key={link.href} href={link.href} onClick={() => setOpen(false)}>
                {link.label}
              </Link>
            ))}
            <a href="tel:+918310000000" onClick={() => setOpen(false)}>
              Call to book 83100 00000
            </a>
            {customer ? (
              <button type="button" className="text-left" onClick={signOut}>
                Sign out ({customer.name})
              </button>
            ) : (
              <>
                <Link href="/login" onClick={() => setOpen(false)}>
                  Sign in
                </Link>
                <Link href="/login?as=operator" onClick={() => setOpen(false)}>
                  Operator
                </Link>
              </>
            )}
          </div>
        </div>
      ) : null}
    </header>
  );
}
