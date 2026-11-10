"use client";

import { ReactNode } from "react";

export const control = "w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm";
export const button = "rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-black disabled:opacity-50";
export const panel = "space-y-4 rounded-xl border border-neutral-200 bg-white p-5";
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block space-y-1 text-sm font-medium"><span>{label}</span>{children}</label>;
}
export function Notice({ message }: { message: string }) {
  return message ? <p role="status" className="my-4 rounded-lg bg-amber-50 p-3 text-sm text-neutral-900">{message}</p> : null;
}
export function errorText(error: unknown) { return error instanceof Error ? error.message : "The action could not be completed"; }
