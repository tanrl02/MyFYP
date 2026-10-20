"use client";
import { Booking, queueToken, visitWindow } from "@smart-skin/shared";
import { useEffect, useRef } from "react";

export default function MissedVisitReview({visit,busy,changed,onConfirm,onCancel}:{visit:Booking;busy:boolean;changed:boolean;onConfirm:()=>void;onCancel:()=>void}){
  const title=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{title.current?.focus();},[]);
  return <section aria-label="Missed appointment confirmation" className="panel mb-6">
    <h2 ref={title} tabIndex={-1} className="text-xl font-semibold">Mark appointment as missed?</h2>
    <p className="my-3 font-semibold">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name}</p>
    <p className="muted mb-3">{visitWindow(visit)} (Malaysia time)</p>
    <p className="mb-3">Confirm only if this patient did not attend. This records a missed appointment and removes it from the waiting queue. The patient can book another appointment.</p>
    {changed?<p role="alert" className="mb-3 text-red-800">The visit changed. Cancel and review its latest status.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||changed} onClick={onConfirm}>{busy?"Saving…":"Confirm missed appointment"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Keep appointment unchanged</button></div>
  </section>;
}
