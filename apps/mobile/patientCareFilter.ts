import type { Care } from "@smart-skin/shared";

export const careFilterLabels = {
  all: "All records",
  dispensing: "Awaiting dispensing",
  unpaid: "Unpaid bills",
  paid: "Paid bills · simulation",
} as const;
export type CareFilter = keyof typeof careFilterLabels;

export function filterCare(records: Care[], status: CareFilter): Care[] {
  return records.filter(record => {
    if (!record.prescription && !record.invoice) return false;
    if (status === "dispensing") return record.prescription?.status === "issued";
    if (status === "unpaid" || status === "paid") return record.invoice?.status === status;
    return true;
  });
}
