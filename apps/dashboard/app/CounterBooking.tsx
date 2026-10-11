"use client";
import { useEffect, useState } from "react";
import { Booking, DemoApi, DemoDoctor, DemoPatient, Slot, doctorNames, patientNames, queueToken, visitTime } from "@smart-skin/shared";

const requestKey=()=>`counter-${Date.now()}-${Math.random().toString(36).slice(2)}`;
export default function CounterBooking({api,onBooked}:{api:DemoApi;onBooked:(booking:Booking)=>void}){
  const [open,setOpen]=useState(false),[patient,setPatient]=useState<DemoPatient>("patient-ava"),[doctor,setDoctor]=useState<DemoDoctor>("doctor-lim");
  const [slots,setSlots]=useState<Slot[]>([]),[slotId,setSlotId]=useState(""),[request,setRequest]=useState(requestKey);
  const [busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const selected=slots.find(s=>s.id===slotId&&s.doctor_id===doctor);
  useEffect(()=>{
    if(!open)return;
    let active=true,fetching=false;
    async function load(){if(fetching)return;fetching=true;try{const data=await api.slots();if(active)setSlots(data);}catch(e){if(active)setError(e instanceof Error?e.message:"Cannot load times.");}finally{fetching=false;}}
    void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};
  },[api,open]);
  async function save(){
    if(!selected||busy)return;setBusy(true);setError("");
    try{const saved=await api.counterBook(patient,selected.id,request);onBooked(saved);setNotice(`${queueToken(saved)} · ${saved.patient_name} booked with ${saved.doctor_name} · ${visitTime(saved.starts_at)}. The patient can see it under My visits.`);setConfirm(false);setSlotId("");setRequest(requestKey());setSlots(await api.slots());}
    catch(e){setError(e instanceof Error?e.message:"Cannot book. Check the queue before retrying.");}finally{setBusy(false);}
  }
  return <section className="panel mb-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Counter booking</h2><p className="muted mt-2 text-sm">Register a demo patient at the counter using the same shared appointment queue.</p></div><button className="btn secondary" disabled={busy} onClick={()=>{setOpen(!open);setConfirm(false);setError("");}}>{open?"Close counter booking":"New counter booking"}</button></div>
    {notice?<p role="status" className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>:null}
    {open?<div className="mt-5">{error?<p role="alert" className="mb-4 rounded-xl bg-red-50 p-4 text-red-800">{error}</p>:null}<div className="grid gap-4 md:grid-cols-3">
      <label className="text-sm font-semibold">Counter patient<select aria-label="Counter patient" className="mt-2" disabled={busy||confirm} value={patient} onChange={e=>{setPatient(e.target.value as DemoPatient);setRequest(requestKey());setNotice("");setError("");}}>{(Object.keys(patientNames) as DemoPatient[]).map(id=><option key={id} value={id}>{patientNames[id]}</option>)}</select></label>
      <label className="text-sm font-semibold">Counter doctor<select aria-label="Counter doctor" className="mt-2" disabled={busy||confirm} value={doctor} onChange={e=>{setDoctor(e.target.value as DemoDoctor);setSlotId("");setRequest(requestKey());setNotice("");setError("");}}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id=><option key={id} value={id}>{doctorNames[id]}</option>)}</select></label>
      <label className="text-sm font-semibold">Counter appointment<select aria-label="Counter appointment" className="mt-2" disabled={busy||confirm} value={slotId} onChange={e=>{setSlotId(e.target.value);setRequest(requestKey());setNotice("");setError("");}}><option value="">Choose a time</option>{slots.filter(s=>s.doctor_id===doctor).map(s=><option key={s.id} value={s.id} disabled={!s.available}>{visitTime(s.starts_at)} · {s.available} places{s.available?"":" · Full"}</option>)}</select></label>
    </div>{confirm?<div className="mt-4 rounded-xl bg-[#f4f7f6] p-4"><p className="mb-4 text-sm">Book {patientNames[patient]} with {selected?.doctor_name} at {selected?visitTime(selected.starts_at):"the selected time"}? This saves a shared visit and issues a queue number.</p><button className="btn" disabled={busy||!selected?.available} onClick={save}>{busy?"Saving…":"Confirm counter booking"}</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setConfirm(false)}>Keep editing</button></div>:<button className="btn mt-4" disabled={busy||!selected?.available} onClick={()=>setConfirm(true)}>Review counter booking</button>}<p className="muted mt-3 text-xs">Available places refresh every five seconds. The server checks capacity and duplicate bookings again when saving.</p></div>:null}
  </section>;
}
