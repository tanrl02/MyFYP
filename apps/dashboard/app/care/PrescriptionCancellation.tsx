"use client";
import {useEffect,useRef,useState} from "react";
import {Care,DemoActor,DemoApi,Prescription,PrescriptionCancellation as Cancellation,medicineLabel,queueToken,visitTime} from "@smart-skin/shared";

export default function PrescriptionCancellation({api,actor,record,busy,onBusy,onSaved}:{api:DemoApi;actor:DemoActor;record:Care;busy:boolean;onBusy:(value:boolean)=>void;onSaved:(value:Prescription)=>void}){
  const {visit,prescription,invoice}=record;
  const allowed=(actor==="doctor-lim"||actor==="doctor-anita")&&actor===visit.doctor_id;
  const [draft,setDraft]=useState<{version:number;reason:string;review:boolean}|null>(null);
  const [error,setError]=useState("");
  const [audit,setAudit]=useState<Cancellation|null>(null);
  const [refresh,setRefresh]=useState(0);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{let active=true;setAudit(null);setError("");if(allowed&&prescription?.status==="cancelled")void api.prescriptionCancellation(visit.id).then(value=>{if(active)setAudit(value);}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Cannot load cancellation record.");});return()=>{active=false;};},[api,allowed,visit.id,prescription?.status,refresh]);
  useEffect(()=>{if(draft?.review)heading.current?.focus();},[draft?.review]);
  if(!allowed||!prescription)return null;
  const eligible=visit.status==="called"&&!visit.consultation_finished_at&&prescription.status==="issued"&&!invoice&&!!prescription.version;
  const changed=!!draft&&(!eligible||draft.version!==prescription.version);
  async function save(){
    if(!draft?.review||busy||changed)return;
    onBusy(true);setError("");
    try{onSaved(await api.cancelPrescription(visit.id,draft.version,draft.reason));setDraft(null);}
    catch(e){setError(e instanceof Error?e.message:"Cannot cancel prescription.");}
    finally{onBusy(false);}
  }
  return <section aria-label="Prescription cancellation" className="my-4 rounded-xl border border-[#ccdcd4] p-4">
    <h4 className="font-semibold">Prescription cancellation</h4>
    {error?<p role="alert" className="my-3 text-red-800">{error}</p>:null}
    {prescription.status==="cancelled"?<>{audit?<><p className="my-3 text-sm">Cancelled by {visit.doctor_name} · {visitTime(audit.created_at)} · reviewed revision {audit.version}</p><p className="whitespace-pre-wrap break-words text-sm">Reason: {audit.reason}</p></>:<p className="my-3 text-sm">{error?"Cancellation record unavailable.":"Loading cancellation record…"}</p>}<button className="mt-3 text-sm underline" disabled={busy} onClick={()=>setRefresh(value=>value+1)}>Refresh cancellation record</button></>:!draft?<>{eligible?<button className="btn secondary mt-3" disabled={busy} onClick={()=>{setError("");setDraft({version:prescription.version!,reason:"",review:false});}}>Cancel prescription</button>:<p className="muted mt-2 text-sm">Cancellation is available before doctor handover, dispensing or billing while the consultation is open.</p>}</>:<>
      {changed?<p role="alert" className="my-3 text-red-800">This visit or prescription changed. Keep the prescription and reopen cancellation to review the latest state.</p>:null}
      {draft.review?<section aria-label="Prescription cancellation review" className="my-3 rounded-lg bg-[#f4f7f6] p-3">
        <h5 ref={heading} tabIndex={-1} className="font-semibold">Review prescription cancellation</h5>
        <p className="my-3 text-sm">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)} · revision {draft.version}</p>
        <ul>{prescription.items.map(item=><li key={item.medicine_id} className="my-2 text-sm"><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="whitespace-pre-wrap break-words">{item.directions}</p></li>)}</ul>
        <p className="my-3 whitespace-pre-wrap break-words text-sm">Reason: {draft.reason}</p>
        <p className="my-3 text-sm">This prescription will remain in the record as Cancelled. Its medicines cannot be dispensed or included in the bill. Stock stays unchanged. This action cannot be undone; issuing a replacement is not available yet.</p>
        <button className="btn" disabled={busy||changed} onClick={save}>{busy?"Saving…":"Confirm prescription cancellation"}</button>
        <button className="btn secondary mt-3" disabled={busy||changed} onClick={()=>setDraft({...draft,review:false})}>Edit cancellation reason</button>
      </section>:<fieldset disabled={busy||changed}>
        <label className="my-3 block text-sm font-semibold">Cancellation reason<textarea maxLength={300} className="mt-2 w-full rounded-lg border p-2 font-normal" value={draft.reason} onChange={event=>setDraft({...draft,reason:event.target.value})}/></label>
        <button className="btn" disabled={!draft.reason.trim()} onClick={()=>{setError("");setDraft({...draft,reason:draft.reason.trim(),review:true});}}>Review prescription cancellation</button>
      </fieldset>}
      <button className="btn secondary mt-3" disabled={busy} onClick={()=>{setDraft(null);setError("");}}>Keep prescription unchanged</button>
    </>}
  </section>;
}
