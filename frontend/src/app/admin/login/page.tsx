"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@bgmtravels.in");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/v1/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="bg-brand px-4 py-2.5">
        <p className="font-display text-[1.45rem] font-bold tracking-wide text-white">BGM TRAVELS</p>
      </div>
      <div className="flex items-center justify-center px-4 py-16">
        <form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-neutral-200 bg-white p-8 shadow-[0_12px_40px_rgba(0,0,0,0.08)]">
          <p className="text-sm font-semibold text-teal">Operator access</p>
          <h1 className="mt-2 text-2xl font-semibold text-navy">BGM Travels admin</h1>
          <input className="mt-6 w-full rounded-lg border border-neutral-300 bg-white px-3 py-3" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input type="password" placeholder="Password" className="mt-3 w-full rounded-lg border border-neutral-300 bg-white px-3 py-3" value={password} onChange={(e) => setPassword(e.target.value)} />
          {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
          <button className="mt-5 w-full rounded-lg bg-brand py-3 font-bold text-black">Sign in</button>
          <p className="mt-4 text-center text-sm text-navy/60">
            Traveller? <a href="/login" className="font-semibold text-teal">Sign in here</a>
          </p>
        </form>
      </div>
    </div>
  );
}
