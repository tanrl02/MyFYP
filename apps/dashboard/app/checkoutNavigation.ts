import type { Booking } from "@smart-skin/shared";

export type CheckoutTarget = { doctor: string; date: string; visit: string };

export function readCheckoutTarget(search: string): CheckoutTarget | null {
  const params = new URLSearchParams(search);
  const doctor = params.get("doctor") || "";
  const date = params.get("date") || "";
  const visit = params.get("checkout_visit") || "";
  if (!["doctor-lim", "doctor-anita"].includes(doctor) || !/^\d{4}-\d{2}-\d{2}$/.test(date)
    || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(visit)) return null;
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) return null;
  return { doctor, date, visit };
}

export function checkoutLink(path: "/" | "/care", target: CheckoutTarget): string {
  return `${path}?${new URLSearchParams({ doctor: target.doctor, date: target.date, checkout_visit: target.visit })}`;
}

export function visitCheckoutTarget(visit: Booking): CheckoutTarget {
  return { doctor: visit.doctor_id, date: visit.clinic_date, visit: visit.id };
}
