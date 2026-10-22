"use client";
import {useEffect,useRef,useState} from "react";
import {BatchStockOverview,DemoApi} from "@smart-skin/shared";
type Batch=BatchStockOverview["batches"][number];
const requestKey=()=>`batch-hold-${Date.now()}-${Math.random().toString(36).slice(2)}`;
export default function BatchHoldForm({api,medicineId,batch,onSaved,onClose,onBusyChange}:{api:DemoApi;medicineId:string;batch:Batch;onSaved:()=>void;onClose:()=>void;onBusyChange:(busy:boolean)=>void}){
  const [source,setSource]=useState(batch),[held]=useState(!batch.held),[reason,setReason]=useState(""),[review,setReview]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[request,setRequest]=useState(requestKey);
  const heading=useRef<HTMLHeadingElement>(null);useEffect(()=>{heading.current?.focus();},[]);
  const valid=!!reason.trim()&&reason.length<=300&&source.held!==held;
  function pending(value:boolean){setBusy(value);onBusyChange(value);}
  async function reload(){if(busy)return;pending(true);setError("");try{const latest=(await api.batchStockOverview(medicineId)).batches.find(row=>row.receipt_id===source.receipt_id);if(!latest)throw new Error("Tracked batch is no longer available.");setSource(latest);setReview(false);setRequest(requestKey());}catch(e){setError(e instanceof Error?e.message:"Cannot reload batch.");}finally{pending(false);}}
  async function save(){if(busy||!review||!valid)return;pending(true);setError("");try{await api.setBatchHold(medicineId,source.receipt_id,{held,reason:reason.trim(),version:source.hold_version,request_id:request});onSaved();}catch(e){setError(e instanceof Error?e.message:"Cannot change batch hold.");}finally{pending(false);}}
  return <section className="panel mt-5" aria-label="Batch hold review"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{held?"Place batch on hold":"Release batch hold"}</h2><p className="my-3 break-words">Batch {source.batch_number} · expiry {source.expiry_date} · {source.remaining_units} units</p><p className="muted mb-3 break-all text-sm">Receipt {source.receipt_id} · hold version {source.hold_version}</p>
    {source.held?<p className="mb-3 whitespace-pre-wrap break-words">Current hold reason: {source.hold_reason}</p>:null}
    <p className="muted mb-4 text-sm">{held?"This receipt batch will stay in physical stock but cannot be used for dispensing or earliest-expiry allocation.":"This removes the hold. Expiry and available-quantity checks still apply before dispensing."} Stock quantities and issued records stay unchanged. The reason, staff identity and time are retained.</p>
    {error?<p role="alert" className="my-3 text-red-800">{error}</p>:null}{source.held===held?<p role="status" className="mb-3">This batch already has the requested state. Close this form to return to the overview.</p>:null}
    <label className="block">Reason<textarea aria-label="Batch hold change reason" maxLength={300} value={reason} disabled={busy||review} onChange={e=>{setReason(e.target.value);setRequest(requestKey());setError("");}} className="mt-2 w-full rounded-lg border p-3"/></label>
    {review?<div className="my-4 rounded-lg border p-4"><h3 className="font-semibold">Review hold change</h3><p className="my-3">{held?"Not on hold → On hold":"On hold → Not on hold"}</p><p className="my-3 whitespace-pre-wrap break-words">{reason.trim()}</p><button className="btn" disabled={busy||!valid} onClick={save}>{busy?"Saving…":held?"Confirm batch hold":"Confirm hold release"}</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setReview(false)}>Keep editing hold</button></div>:<button className="btn mt-4" disabled={busy||!valid} onClick={()=>setReview(true)}>Review hold change</button>}
    <div className="mt-4 flex flex-wrap gap-4"><button className="underline" disabled={busy} onClick={reload}>Reload latest batch</button><button className="underline" disabled={busy} onClick={onClose}>Cancel hold change</button></div>
  </section>;
}
