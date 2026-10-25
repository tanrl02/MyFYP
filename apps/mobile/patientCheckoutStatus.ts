import { statusLabels } from "@smart-skin/shared";
import type { Booking } from "@smart-skin/shared";

export function readyForCheckout(visit: Booking): boolean {
  return visit.status === "called" && !!visit.consultation_finished_at && !visit.rescheduled_to_id;
}

export function patientVisitStatus(visit: Booking): string {
  return visit.rescheduled_to_id ? "Rescheduled" : readyForCheckout(visit) ? "Ready for checkout" : statusLabels[visit.status];
}
