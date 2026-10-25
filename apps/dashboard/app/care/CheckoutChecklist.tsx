import { Care } from "@smart-skin/shared";

export default function CheckoutChecklist({ record }: { record: Care }) {
  const { visit, prescription, invoice } = record;
  const completed = visit.status === "completed";
  const handedOver = !!visit.consultation_finished_at;
  const needsDispensing = !!prescription && prescription.status !== "dispensed";
  const steps = [
    { label: "Doctor handover", status: handedOver ? "Finished" : completed ? "No handover recorded" : "Awaiting doctor handover", done: handedOver },
    { label: "Visit completion", status: completed ? "Completed" : "Awaiting staff completion", done: completed },
    { label: "Medicines", status: prescription ? needsDispensing ? "Awaiting dispensing" : "Dispensed" : "No prescription issued", done: !!prescription && !needsDispensing },
    { label: "Bill", status: invoice ? "Generated" : "Not generated", done: !!invoice },
    { label: "Payment", status: invoice?.status === "paid" ? "Paid · simulation" : invoice ? "Unpaid · simulation" : "Awaiting bill", done: invoice?.status === "paid" },
  ];
  const next = !completed
    ? handedOver
      ? "Complete this visit in the patient queue."
      : "Confirm with the doctor that the consultation is finished, then complete the visit in the patient queue."
    : needsDispensing
      ? "Review and dispense the prescribed medicines below."
      : !invoice
        ? "Review and generate the bill below."
        : invoice.status !== "paid"
          ? "Review and record the simulated payment below."
          : "Checkout complete. The simulated payment has been recorded.";

  return <section aria-label="Checkout checklist" className="mb-5 rounded-xl border border-[#dce6e0] bg-[#f4f7f6] p-4">
    <h3 className="font-semibold">Checkout checklist</h3>
    <dl className="my-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{steps.map(step => <div key={step.label}>
      <dt className="text-sm font-semibold">{step.label}</dt>
      <dd className={`mt-1 text-sm ${step.done ? "text-[#176f5e]" : "muted"}`}>{step.status}</dd>
    </div>)}</dl>
    <p className="text-sm"><strong>{completed && !needsDispensing && invoice?.status === "paid" ? "Checkout: " : "Next: "}</strong>{next}</p>
    {!completed ? <a className="mt-2 inline-block text-sm font-semibold underline" href="/">Open patient queue</a> : null}
    {!handedOver && completed ? <p className="muted mt-2 text-xs">Staff completed this visit without a recorded doctor handover. Its saved dispensing, bill and payment remain valid.</p> : null}
  </section>;
}
