"use client";
import {useEffect,useRef,useState} from "react";
import {DemoApi,Medicine,medicineLabel} from "@smart-skin/shared";
const requestKey=()=>`stock-threshold-${Date.now()}-${Math.random().toString(36).slice(2)}`;
export default function StockThresholdForm({api,item,onSaved,onClose}:{api:DemoApi;item:Medicine;onSaved:()=>void;onClose:()=>void}){
  const [source,setSource]=useState(item),[value,setValue]=useState(String(item.low_stock_threshold));
  const [review,setReview]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[request,setRequest]=useState(requestKey);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus();},[]);
  const threshold=Number(value),valid=/^\d+$/.test(value)&&Number.isInteger(threshold)&&threshold>=0&&threshold<=99999&&threshold!==source.low_stock_threshold;
  async function reload(){if(busy)return;setBusy(true);setError("");try{const latest=(await api.medicines()).find(m=>m.id===source.id);if(!latest)throw new Error("Medicine no longer available.");setSource(latest);setValue(String(latest.low_stock_threshold));setReview(false);setRequest(requestKey());}catch(e){setError(e instanceof Error?e.message:"Cannot reload item.");}finally{setBusy(false);}}
  async function save(){if(!valid||!review||busy)return;setBusy(true);setError("");try{await api.setMedicineThreshold(source.id,{low_stock_threshold:threshold,version:source.version,request_id:request});onSaved();}catch(e){setError(e instanceof Error?e.message:"Cannot save alert level.");}finally{setBusy(false);}}
  return <section className="panel mb-6" aria-label="Item alert level editor"><h2 ref={heading} tabIndex={-1} className="text-lg font-semibold">Set low-stock alert level</h2><p className="my-3 font-semibold">{medicineLabel(source)}</p><p className="muted my-3 text-sm">An active item needs replenishment when its quantity is at or below this level. Zero means alert only when empty. Inactive items are excluded from inventory-report alerts.</p>
    {error?<p role="alert" className="my-3 rounded-lg bg-red-50 p-3 text-red-800">{error}</p>:null}
    <label className="block">Low-stock alert level (units)<input aria-label="Low-stock alert level (units)" type="number" min="0" max="99999" step="1" disabled={busy||review} value={value} onChange={e=>{setValue(e.target.value);setRequest(requestKey());setError("");}} className="mt-2 block w-48 rounded-lg border p-3"/></label><p className="muted my-3 text-sm">Whole numbers from 0 to 99,999. Current alert level: {source.low_stock_threshold} units.</p>
    {review?<div className="my-4 rounded-xl bg-[#f4f7f6] p-4"><h3 className="font-semibold">Review alert level</h3><p className="my-3">{source.low_stock_threshold} → {threshold} units{threshold===0?" · alert only when empty":""}.</p><p className="mb-3 text-sm">This changes stock alerts. Stock quantities, prices, prescriptions and bills stay unchanged.</p><button className="btn" disabled={busy||!valid} onClick={save}>{busy?"Saving…":"Confirm alert level"}</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setReview(false)}>Keep editing</button></div>:<button className="btn" disabled={busy||!valid} onClick={()=>setReview(true)}>Review alert level</button>}
    <div className="mt-4 flex flex-wrap gap-4"><button className="text-sm underline" disabled={busy} onClick={reload}>Reload latest item</button><button className="text-sm underline" disabled={busy} onClick={onClose}>Cancel alert editing</button></div><p className="muted mt-2 text-xs">Reload replaces your unsaved alert level with the latest value.</p>
  </section>;
}
