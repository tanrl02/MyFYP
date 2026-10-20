import type { DailyReport } from "@smart-skin/shared";

// Neutralise spreadsheet formulas in catalogue text, then apply CSV quoting.
function csvCell(value: string | number): string {
  const text = typeof value === "string" && (/^[\s\uFEFF]*[=+\-@]/u.test(value) || /^[\t\r\n]/u.test(value)) ? "'" + value : String(value);
  return `"${text.replace(/"/g, '\"\"')}"`;
}

export function dailyReportCsv(report: DailyReport): string {
  type Row = (string | number)[];
  const rows: Row[] = [["Section", "Metric", "Record ID", "Record name", "Value", "Unit", "Date basis", "Notes"]];
  const add = (section: string, metric: string, value: string | number, unit = "", basis = "", notes = "", id = "", name = "") => rows.push([section, metric, id, name, value, unit, basis, notes]);
  add("Report", "Title", "Daily clinic report");
  add("Report", "Report date", report.clinic_date, "", "Malaysia clinic date");
  add("Report", "Generated at", report.generated_at, "ISO 8601 timestamp");
  add("Report", "Timezone", report.timezone);
  add("Report", "Data label", "Synthetic demonstration; billing and payments simulated; no money moves.");
  const appointment = "Appointment date";
  for (const [key, label] of [["total", "Booking records"], ["waiting", "Waiting"], ["called", "Called"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["missed", "Missed"], ["rescheduled", "Rescheduled"]] as const) {
    add("Visits", label, report.visits[key], "visits", appointment, key === "total" ? "Includes rescheduled original booking records." : "Current saved status.");
  }
  for (const doctor of report.visits_by_doctor) {
    for (const [key, label] of [["total", "Booking records"], ["waiting", "Waiting"], ["called", "Called"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["missed", "Missed"], ["rescheduled", "Rescheduled"]] as const) {
      add("Visits by doctor", label, doctor.visits[key], "visits", appointment, "Current saved status; rescheduled originals are separate from cancellations.", doctor.doctor_id, doctor.doctor_name);
    }
  }
  add("Billing - simulation", "Invoice count", report.billing.invoice_count, "invoices", appointment);
  for (const [key, label] of [["billed_cents", "Billed"], ["paid_cents", "Paid"], ["unpaid_cents", "Unpaid"]] as const) {
    add("Billing - simulation", label, (report.billing[key] / 100).toFixed(2), "MYR (simulated)", appointment, "Current invoice status; paid totals are not cash collected on this date.");
  }
  const activity = "Activity date in Malaysia time";
  const movementNote = "Saved movements, not closing stock balances; independent of appointment date.";
  add("Stock totals", "Received", report.stock.received_units, "units", activity, movementNote);
  add("Stock totals", "Dispensed", report.stock.dispensed_units, "units", activity, movementNote);
  add("Stock totals", "Damaged/lost", report.stock.lost_units, "units", activity, movementNote);
  for (const item of report.stock.items) {
    for (const [key, label] of [["received", "Received"], ["dispensed", "Dispensed"], ["lost", "Damaged/lost"]] as const) {
      add("Stock items", label, item[key], "units", activity, movementNote, item.medicine_id, item.name);
    }
  }
  add("Feedback", "Submitted ratings", report.feedback.count, "ratings", "Submission date in Malaysia time");
  add("Feedback", "Average rating", report.feedback.average_rating === null ? "" : report.feedback.average_rating.toFixed(2), "out of 5", "Submission date in Malaysia time", report.feedback.average_rating === null ? "No ratings; no average yet." : "");
  // UTF-8 BOM supports Excel; CRLF and quoted cells preserve commas/newlines.
  return "\uFEFF" + rows.map(row => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

export function downloadDailyReport(report: DailyReport): void {
  const url = URL.createObjectURL(new Blob([dailyReportCsv(report)], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `smart-skin-daily-report-${report.clinic_date}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Keep the object URL alive until the browser has begun the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
