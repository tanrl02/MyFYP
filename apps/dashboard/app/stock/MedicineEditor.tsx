"use client";
import {useEffect,useRef,useState} from "react";
import {DemoApi,Medicine,medicineLabel,money} from "@smart-skin/shared";
const requestKey=()=>`medicine-edit-${Date.now()}-${Math.random().toString(36).slice(2)}`;
export default function MedicineEditor({api,item,onSaved,onClose}:{api:DemoApi;item:Medicine;onSaved:()=>void;onClose:()=>void}){
  const [source,setSource]=useState(item),[name,setName]=useState(item.name),[price,setPrice]=useState((item.price_cents/100).toFixed(2));
  const [review,setReview]=useState(false),[busy,setBusy]=useState(false),[request,setRequest]=useState(requestKey),[error,setError]=useState("");
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus();},[]);
  const cents=Math.round(Number(price)*100),changed=name.trim()!==source.name||cents!==source.price_cents;
  const valid=!!name.trim()&&name.length<=100&&/^\d+(\.\d{1,2})?$/.test(price)&&Number.isSafeInteger(cents)&&cents>=0&&cents<=1000000&&changed;
  function change(){setRequest(requestKey());setError("");}
  async function reload(){if(busy)return;setBusy(true);setError("");try{const latest=(await api.medicines()).find(m=>m.id===source.id);if(!latest)throw new Error("Medicine no longer available.");setSource(latest);setName(latest.name);setPrice((latest.price_cents/100).toFixed(2));setReview(false);setRequest(requestKey());}catch(e){setError(e instanceof Error?e.message:"Cannot reload catalogue item.");}finally{setBusy(false);}}
  async function save(){if(!review||!valid||busy)return;setBusy(true);setError("");try{await api.editMedicine(source.id,{name:name.trim(),price_cents:cents,version:source.version,request_id:request});onSaved();}catch(e){setError(e instanceof Error?e.message:"Cannot update catalogue item.");}finally{setBusy(false);}}
  return <section className="panel mb-6"><h2 ref={heading} tabIndex={-1} className="text-lg font-semibold">Edit catalogue name and price</h2><p className="muted my-3 text-sm">{medicineLabel(source)} · version {source.version}. Strength and dosage form stay fixed. Stock is managed through receiving and dispensing. Issued prescriptions and bills keep their saved names and prices.</p>
    {error?<p role="alert" className="my-3 rounded-lg bg-red-50 p-3 text-red-800">{error}</p>:null}
    <div className="grid gap-4 md:grid-cols-2"><label>Medicine name<input aria-label="Edit medicine name" required maxLength={100} disabled={busy||review} value={name} onChange={e=>{setName(e.target.value);change();}} className="mt-2 w-full rounded-lg border p-3"/></label><label>Unit price (RM)<input aria-label="Edit unit price (RM)" maxLength={8} inputMode="decimal" disabled={busy||review} value={price} onChange={e=>{setPrice(e.target.value);change();}} className="mt-2 w-full rounded-lg border p-3"/></label></div>
    <p className="muted my-3 text-sm">RM 0.00–10,000.00 per unit, up to two decimal places. Price changes apply to prescriptions issued after saving.</p>
    {review?<div className="my-4 rounded-xl bg-[#f4f7f6] p-4"><h3 className="font-semibold">Review catalogue change</h3><p className="mt-3 break-words">Name: {source.name} → {name.trim()}</p><p className="my-3">Unit price: {money(source.price_cents)} → {money(cents)}</p><p className="mb-3 text-sm">Confirm this item update? Existing stock, prescriptions and bills stay unchanged.</p><button className="btn" disabled={busy} onClick={save}>{busy?"Saving…":"Confirm catalogue change"}</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setReview(false)}>Keep editing</button></div>:<button className="btn mt-3" disabled={busy||!valid} onClick={()=>{setReview(true);setError("");}}>Review catalogue change</button>}
    <div className="mt-4 flex flex-wrap gap-4"><button className="text-sm underline" disabled={busy} onClick={reload}>Reload latest item</button><button className="text-sm underline" disabled={busy} onClick={onClose}>Cancel catalogue editing</button></div><p className="muted mt-2 text-xs">Reload replaces unsaved edits with the latest catalogue values.</p>
  </section>;
}
