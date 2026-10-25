"use client";
import { useEffect, useRef } from "react";
import { Booking, queueToken, visitWindow } from "@smart-skin/shared";

export default function CompleteVisitReview({ visit, busy, changed, unavailable, onConfirm, onCancel }: {
  visit: Booking; busy: boolean; changed: boolean; unavailable: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, []);
  return <section aria-label="Visit completion review" className="panel mb-6">
    <h2 ref={title} tabIndex={-1} className="text-xl font-semibold">Complete this visit?</h2>
    <p className="my-3 font-semibold">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name}</p>
    <p className="muted mb-3">{visitWindow(visit)} (Malaysia time)</p>
    <p className="mb-3">{visit.consultation_finished_at ? "Doctor handover: Finished — ready for checkout." : "No doctor handover recorded. Confirm with the doctor that the consultation is finished."}</p>
    <p className="muted mb-3">Confirmation marks this visit Completed. Continue with dispensing and billing in Care & bills.</p>
    {changed ? <p role="alert" className="mb-3 text-red-800">The visit changed. Cancel and review its latest status.</p> : unavailable ? <p role="alert" className="mb-3 text-red-800">Current queue information is unavailable. Refresh the queue before confirming.</p> : null}
    <div className="flex flex-wrap gap-3">
      <button className="btn" disabled={busy || changed || unavailable} onClick={onConfirm}>{busy ? "Saving…" : "Confirm complete visit"}</button>
      <button className="btn secondary" disabled={busy} onClick={onCancel}>Keep visit unchanged</button>
    </div>
  </section>;
}
