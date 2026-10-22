import type { BillingSummary, BillingTotals } from "@smart-skin/shared";

function cell(value: string | number): string {
  const text=String(value);
  const safe=typeof value==="string" && /^[\s]*[=+\-@]/.test(text)?`'${text}`:text;
  return `"${safe.replace(/"/g,'""')}"`;
}

export function billingReportCsv(report: BillingSummary): string {
  const rows: (string | number)[][]=[[
    "Report", "Period", "Period start", "Period end", "Timezone", "Generated at (ISO)",
    "Row type", "Issue period start", "Issue period end", "Invoices", "Paid invoices", "Unpaid invoices",
    "Billed (MYR)", "Paid (MYR, simulation)", "Outstanding (MYR)", "Date basis", "Notes"
  ]];
  const add=(kind:string,start:string,end:string,totals:BillingTotals)=>rows.push([
    "Synthetic billing analysis - simulation; no money moves.",report.period,report.start_date,report.end_date,
    report.timezone,report.generated_at,kind,start,end,totals.invoice_count,totals.paid_invoice_count,
    totals.unpaid_invoice_count,(totals.billed_cents/100).toFixed(2),(totals.paid_cents/100).toFixed(2),
    (totals.unpaid_cents/100).toFixed(2),"Invoice issue date in Malaysia time (UTC+8)",
    "Current payment status, including later simulated payments; not cash collected during this period. Outstanding covers only invoices issued in this period, not all clinic debt."
  ]);
  add("Period total",report.start_date,report.end_date,report.billing);
  for(const bucket of report.buckets)add(report.granularity==="day"?"Issue date":"Issue month",bucket.start_date,bucket.end_date,bucket.billing);
  return "\uFEFF"+rows.map(row=>row.map(cell).join(",")).join("\r\n")+"\r\n";
}

export function downloadBillingReport(report: BillingSummary): void {
  const url=URL.createObjectURL(new Blob([billingReportCsv(report)],{type:"text/csv;charset=utf-8"}));
  const link=document.createElement("a");
  link.href=url;
  link.download=`smart-skin-billing-${report.period}-${report.start_date}-${report.end_date}.csv`;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
