"use client";
import { Booking, queueToken, visitWindow } from "@smart-skin/shared";
import { useEffect, useRef } from "react";

export default function MissedVisitReview({visit,mode="mark",busy,changed,onConfirm,onCancel}:{visit:Booking;mode?:"mark"|"restore";busy:boolean;changed:boolean;onConfirm:()=>void;onCancel:()=>void}){
  const restoring=mode==="restore";
  const title=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{title.current?.focus();},[]);
  return <section aria-label={restoring?"Restore waiting confirmation":"Missed appointment confirmation"} className="panel mb-6">
    <h2 ref={title} tabIndex={-1} className="text-xl font-semibold">{restoring?"Restore this visit to waiting?":"Mark appointment as missed?"}</h2>
    <p className="my-3 font-semibold">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name}</p>
    <p className="muted mb-3">{visitWindow(visit)} (Malaysia time)</p>
    {restoring?<><p className="mb-3">Use this to correct a mistaken missed status or record a late arrival. The same visit returns to the queue with its original number and appointment time. An audit event records the correction.</p><p className="muted mb-3">Previously revoked assessment access stays closed. The patient can share again using the existing sharing flow if needed.</p></>:<p className="mb-3">Confirm only if this patient did not attend. This records a missed appointment and removes it from the waiting queue. The patient can book another appointment.</p>}
    {changed?<p role="alert" className="mb-3 text-red-800">The visit changed. Cancel and review its latest status.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||changed} onClick={onConfirm}>{busy?"Saving…":restoring?"Confirm restore to waiting":"Confirm missed appointment"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Keep appointment unchanged</button></div>
  </section>;
}
