"use client";
import {useEffect,useState} from "react";
import {Care,Medicine,DemoApi,DispensingStock,DispensingAllocation,medicineLabel,queueToken,visitTime} from "@smart-skin/shared";
import {earliestExpiryQuantities} from "./earliestExpiry";

export default function DispensingReview({api,record,catalog,busy,onConfirm,onCancel}:{api:DemoApi;record:Care;catalog:Medicine[];busy:boolean;onConfirm:(allocations:DispensingAllocation[])=>Promise<void>;onCancel:()=>void}){
  const {visit,prescription}=record;
  const [submitError,setSubmitError]=useState("");
  const [prepared,setPrepared]=useState(false);
  const [stock,setStock]=useState<DispensingStock|null>(null),[error,setError]=useState(""),[quantities,setQuantities]=useState<Record<string,string>>({});
  useEffect(()=>{let active=true,fetching=false;async function load(){if(!prescription||fetching)return;fetching=true;try{const result=await api.dispensingStock(prescription.id);if(active){setStock(result);setError("");}}catch(e){if(active){setStock(null);setError(e instanceof Error?e.message:"Cannot load stock sources.");}}finally{fetching=false;}}void load();const timer=setInterval(load,3000);return()=>{active=false;clearInterval(timer);};},[api,prescription?.id]);
  if(!prescription)return null;
  const allocations:DispensingAllocation[]=[];
  let valid=!!stock&&stock.status==="issued";
  const groups=prescription.items.map(item=>{
    const current=stock?.items.find(row=>row.medicine_id===item.medicine_id);
    const sources=[{receipt_id:null as string|null,label:"Untracked stock · verify physical expiry",available:current?.untracked_units??0,expired:false,held:false},...(current?.batches??[]).map(batch=>({receipt_id:batch.receipt_id,label:`${batch.batch_number} · expiry ${batch.expiry_date} · receipt ${batch.receipt_id.slice(0,8)}`,available:batch.remaining_units,expired:batch.expired,held:batch.held}))];
    let total=0;
    const rows=sources.map(source=>{
      const key=`${item.medicine_id}|${source.receipt_id??""}`;
      const value=quantities[key]??(source.receipt_id===null&&source.available>=item.quantity?String(item.quantity):"0");
      const count=Number(value);
      if(!/^\d+$/.test(value)||!Number.isInteger(count)||count<0||count>source.available||((source.expired||source.held)&&count>0))valid=false;
      total+=count;
      if(count>0)allocations.push({medicine_id:item.medicine_id,receipt_id:source.receipt_id,quantity:count});
      return {...source,key,value};
    });
    if(total!==item.quantity||!current||current.stock<item.quantity)valid=false;
    return {item,rows,total};
  });
  async function submit(){if(busy||!valid)return;setSubmitError("");try{await onConfirm(allocations);}catch(e){setSubmitError(e instanceof Error?e.message:"Cannot dispense. Review stock sources before retrying.");}}
  return <section aria-label="Dispensing review" className="mt-4 rounded-xl border border-[#ccdcd4] bg-[#f4f7f6] p-4"><h4 className="font-semibold">Review dispensing · select stock sources</h4><p className="my-3">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)}</p>
    <p className="muted my-3 text-sm">Allocate each required quantity across one or more sources. Expired or held batches cannot be used. Untracked stock includes older stock whose batch balances could not be reconstructed; verify its physical expiry before dispensing.</p>
    <button className="btn secondary" disabled={busy||!stock||stock.status!=="issued"} onClick={()=>{if(!stock)return;setQuantities(earliestExpiryQuantities(prescription.items,stock));setSubmitError("");setPrepared(true);}}>Use earliest-expiring stock</button><p className="muted my-2 text-sm">Replaces entered quantities using unexpired tracked batches that are not on hold, earliest expiry first. Leaves untracked stock at zero. Review shortages and confirm separately.</p>
    {prepared?<p role="status" className="my-3 text-sm">Tracked-batch quantities prepared. Review the allocations and any shortfalls below before confirming.</p>:null}
    {submitError?<p role="alert" className="my-3 text-red-800">{submitError}</p>:null}
    {error?<p role="alert" className="my-3 text-red-800">{error} Retrying automatically.</p>:!stock?<p role="status">Loading stock sources…</p>:null}
    {groups.map(({item,rows,total})=><section className="my-4 rounded-lg border p-3" key={item.medicine_id}><h5 className="font-semibold">{medicineLabel(item)} × {item.quantity}</h5><p className="muted my-2 text-sm whitespace-pre-wrap break-words">{item.directions}</p><p className="my-2 text-sm">Allocated {total} of {item.quantity} required · Current total stock: {catalog.find(m=>m.id===item.medicine_id)?.stock??"Unavailable"}</p>{total<item.quantity?<p className="my-2 font-semibold text-amber-900">Short by {item.quantity-total} {item.quantity-total===1?"unit":"units"}. Choose another available source or receive more stock.</p>:null}
      {rows.map(row=><label key={row.key} className="my-3 block text-sm">{row.label} · {row.available} available{row.expired?" · Expired · blocked":""}{row.held?" · On hold · blocked":""}<input aria-label={`${medicineLabel(item)} allocation from ${row.label}`} type="number" min="0" max={Math.min(item.quantity,row.available)} step="1" value={row.value} disabled={busy||!stock||((row.expired||row.held||row.available===0)&&Number(row.value)===0)} onChange={e=>{setSubmitError("");setPrepared(false);setQuantities(current=>({...current,[row.key]:e.target.value}));}} className="mt-2 block w-28 rounded-lg border bg-white p-2"/></label>)}
    </section>)}
    <p className="muted my-3 text-sm">Sources refresh every three seconds. Confirmation rechecks expiry and quantities and saves all allocations with the stock deduction in one transaction.</p>{stock&&!valid?<p role="alert" className="my-3 text-red-800">Match every required quantity using available, unexpired stock sources.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||!valid} onClick={submit}>{busy?"Saving…":"Confirm dispensing"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Cancel dispensing</button></div>
  </section>;
}
