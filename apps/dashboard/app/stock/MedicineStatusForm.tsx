"use client";
import {useEffect,useRef,useState} from "react";
import {DemoApi,Medicine,medicineLabel} from "@smart-skin/shared";
export default function MedicineStatusForm({api,item,onSaved,onClose}:{api:DemoApi;item:Medicine;onSaved:()=>void;onClose:()=>void}){
  const active=!item.active;
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [request]=useState(()=>`medicine-status-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus();},[]);
  async function save(){if(busy)return;setBusy(true);setError("");try{await api.setMedicineActive(item.id,{active,version:item.version,request_id:request});onSaved();}catch(e){setError(e instanceof Error?e.message:"Cannot change item status.");}finally{setBusy(false);}}
  return <section className="panel mb-6"><h2 ref={heading} tabIndex={-1} className="text-lg font-semibold">{active?"Reactivate catalogue item":"Mark catalogue item inactive"}</h2><p className="my-3 font-semibold">{medicineLabel(item)}</p><p className="my-3">Status: {item.active?"Active → Inactive":"Inactive → Active"}</p><p className="muted my-3 text-sm">{active?"This item will be available for new prescriptions again.":"This item will no longer be offered for new prescriptions. Staff will still see it in the stock catalogue."} Stock, existing prescriptions and bills stay unchanged. Already-issued prescriptions can still be dispensed using the usual stock checks. Receiving stock remains available.</p>{error?<p role="alert" className="my-3 rounded-lg bg-red-50 p-3 text-red-800">{error} Close this review and select the current item to try again.</p>:null}<button className="btn" disabled={busy} onClick={save}>{busy?"Saving…":active?"Confirm reactivation":"Confirm inactive status"}</button><button className="btn secondary ml-3" disabled={busy} onClick={onClose}>Cancel status change</button></section>;
}
