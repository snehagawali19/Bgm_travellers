"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { SiteShell } from "@/components/SiteShell";
import { api } from "@/lib/api";

type Mode = "login" | "register";
type Role = "customer" | "operator";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("as") || params.get("role");
  const [role, setRole] = useState<Role>(requested === "operator" ? "operator" : "customer");
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState(role === "operator" ? "admin@bgmtravels.in" : "user@bgmtravels.in");
  const [phone, setPhone] = useState("9876543210");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function switchRole(next: Role) {
    setRole(next);
    setMode("login");
    setError("");
    setEmail(next === "operator" ? "admin@bgmtravels.in" : "user@bgmtravels.in");
    setPassword("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (role === "operator") {
        await api("/api/v1/admin/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        router.push("/admin");
        return;
      }
      if (mode === "register") {
        await api("/api/v1/auth/register", {
          method: "POST",
          body: JSON.stringify({ name, email, phone, password }),
        });
      } else {
        await api("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }
      router.push("/my-bookings");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  const field = "w-full rounded-lg border border-neutral-300 bg-white px-3 py-3";

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-3xl font-semibold text-navy">Sign in</h1>
      <p className="mt-2 text-sm text-navy/60">Travellers book tickets. Operators run the dashboard.</p>

      <div className="mt-6 grid grid-cols-2 rounded-lg border border-neutral-200 p-1">
        <button
          type="button"
          onClick={() => switchRole("customer")}
          className={`rounded-md py-2 text-sm font-bold ${role === "customer" ? "bg-brand text-black" : "text-black/60"}`}
        >
          Traveller
        </button>
        <button
          type="button"
          onClick={() => switchRole("operator")}
          className={`rounded-md py-2 text-sm font-bold ${role === "operator" ? "bg-brand text-black" : "text-black/60"}`}
        >
          Operator
        </button>
      </div>

      <form onSubmit={submit} className="mt-6 space-y-3 rounded-2xl border border-neutral-200 bg-white p-6 shadow-[0_12px_40px_rgba(0,0,0,0.08)]">
        {role === "customer" && mode === "register" ? (
          <>
            <input required placeholder="Full name" className={field} value={name} onChange={(e) => setName(e.target.value)} />
            <input required placeholder="Mobile number" className={field} value={phone} onChange={(e) => setPhone(e.target.value)} />
          </>
        ) : null}
        <input
          required
          type="email"
          placeholder="Email"
          className={field}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          required
          type="password"
          placeholder="Password"
          className={field}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button disabled={busy} className="w-full rounded-lg bg-brand py-3 font-bold text-black">
          {busy ? "Please wait…" : role === "operator" ? "Sign in as operator" : mode === "register" ? "Create account" : "Sign in"}
        </button>
        {role === "customer" ? (
          <>
            <p className="text-center text-sm text-navy/60">
              {mode === "login" ? "New traveller?" : "Already have an account?"}{" "}
              <button type="button" className="font-semibold text-teal" onClick={() => setMode(mode === "login" ? "register" : "login")}>
                {mode === "login" ? "Register" : "Sign in"}
              </button>
            </p>
            {mode === "login" ? (
              <p className="text-center text-xs text-navy/50">Demo traveller: user@bgmtravels.in / User123</p>
            ) : null}
          </>
        ) : (
          <p className="text-center text-xs text-navy/50">Operator dashboard: admin@bgmtravels.in / Admin123</p>
        )}
      </form>
      <p className="mt-4 text-center text-sm">
        <Link href="/" className="text-navy/60 hover:text-navy">
          Back to home
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <SiteShell>
      <Suspense>
        <LoginForm />
      </Suspense>
    </SiteShell>
  );
}
