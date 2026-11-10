export function formatPaise(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

export function formatIST(iso: string, options?: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
    ...options,
  });
}

export function formatISTTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function addDaysISO(days: number): string {
  const now = new Date();
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  ist.setDate(ist.getDate() + days);
  const month = String(ist.getMonth() + 1).padStart(2, "0");
  const day = String(ist.getDate()).padStart(2, "0");
  return `${ist.getFullYear()}-${month}-${day}`;
}

export function todayISO(): string {
  return addDaysISO(0);
}

export function shortDateLabel(iso: string): string {
  return new Date(`${iso}T12:00:00+05:30`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}

export function shiftISO(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00+05:30`);
  date.setDate(date.getDate() + days);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function departureLabel(iso: string): string {
  const label = shortDateLabel(iso);
  if (iso === todayISO()) return `Today, ${label}`;
  if (iso === addDaysISO(1)) return `Tomorrow, ${label}`;
  return label;
}

export function durationLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}
