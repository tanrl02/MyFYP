import type { Care } from "@smart-skin/shared";

export const careFilterLabels = {
  all: "All records",
  dispensing: "Awaiting dispensing",
  awaitingBill: "Awaiting bill",
  unpaid: "Unpaid bills",
  paid: "Paid bills · simulation",
} as const;
export type CareFilter = keyof typeof careFilterLabels;
export const careOrderLabels = { newest: "Newest first", oldest: "Oldest first" } as const;
export type CareOrder = keyof typeof careOrderLabels;

export function summarizeCare(records: Care[]) {
  return records.reduce((summary, record) => {
    if (record.prescription?.status === "issued") summary.awaitingDispensing += 1;
    if (record.invoice?.status === "unpaid") summary.unpaidCents += record.invoice.total_cents;
    if (record.invoice?.status === "paid") summary.paidCents += record.invoice.total_cents;
    return summary;
  }, { unpaidCents: 0, paidCents: 0, awaitingDispensing: 0 });
}

export function sortCare(records: Care[], order: CareOrder): Care[] {
  return [...records].sort((a, b) => {
    const difference = Date.parse(a.visit.starts_at) - Date.parse(b.visit.starts_at);
    if (Number.isFinite(difference) && difference !== 0) return order === "oldest" ? difference : -difference;
    return a.visit.queue_number - b.visit.queue_number || (a.visit.id < b.visit.id ? -1 : a.visit.id > b.visit.id ? 1 : 0);
  });
}

export function filterCare(records: Care[], status: CareFilter, query = "", token?: (visit: Care["visit"]) => string, date: string | null = null): Care[] {
  const search = query.trim().toLowerCase();
  return records.filter(record => {
    if (!record.prescription && !record.invoice) return false;
    if (date && record.visit.clinic_date !== date) return false;
    if (search && !record.visit.doctor_name.toLowerCase().includes(search) && !(token?.(record.visit) ?? "").toLowerCase().includes(search) && !record.prescription?.items.some(item => item.name.toLowerCase().includes(search))) return false;
    if (status === "dispensing") return record.prescription?.status === "issued";
    if (status === "awaitingBill") return !!record.prescription && !record.invoice;
    if (status === "unpaid" || status === "paid") return record.invoice?.status === status;
    return true;
  });
}
