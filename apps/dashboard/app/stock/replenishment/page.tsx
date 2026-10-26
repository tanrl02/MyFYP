"use client";
import {useStaffIdentity} from "../../StaffIdentity";
import {useEffect,useMemo,useRef,useState} from "react";
import {DemoApi,Medicine,medicineLabel} from "@smart-skin/shared";

export default function ReplenishmentPage(){
  const {actor:staffActor,names:staffNames}=useStaffIdentity();
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000",staffActor),[staffActor]);
  const [snapshot,setSnapshot]=useState<{items:Medicine[];refreshedAt:string}|null>(null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  const printing=useRef(false);
  useEffect(()=>{
    let active=true,fetching=false;
    async function load(){
      if(fetching||printing.current)return;fetching=true;
      try{const stock=await api.stock();if(active&&!printing.current){setSnapshot({items:stock.medicines.filter(item=>item.active&&item.stock<=item.low_stock_threshold).sort((a,b)=>a.stock-b.stock||a.name.localeCompare(b.name)||a.id.localeCompare(b.id)),refreshedAt:new Date().toISOString()});setError("");}}
      catch(e){if(active&&!printing.current){setSnapshot(null);setError(e instanceof Error?e.message:"Cannot load replenishment list.");}}
      finally{fetching=false;}
    }
    const beforePrint=()=>{printing.current=true;},afterPrint=()=>{printing.current=false;void load();};
    window.addEventListener("beforeprint",beforePrint);window.addEventListener("afterprint",afterPrint);
    void load();const timer=setInterval(load,5000);
    return()=>{active=false;clearInterval(timer);window.removeEventListener("beforeprint",beforePrint);window.removeEventListener("afterprint",afterPrint);};
  },[api,retry]);
  const total=snapshot?.items.reduce((sum,item)=>sum+Math.max(0,(item.target_stock??item.stock)-item.stock),0)??0;
  return <main className={`replenishment-list mx-auto max-w-5xl px-5 py-8 ${snapshot?"replenishment-ready":""}`}>
    <nav className="replenishment-actions flex flex-wrap gap-5"><a className="underline" href="/stock">← Pharmacy stock</a><a className="underline" href="/stock/reports">Inventory analysis</a></nav>
    <header className="my-6"><h1 className="text-3xl font-semibold">Stock replenishment list</h1><p className="muted mt-3">{staffNames[staffActor]||staffActor} · synthetic items · current stock</p></header>
    <p className="mb-4">Active items at or below their saved alert level, including out-of-stock items. Units to replenish = target stock minus current stock, with a minimum of zero. Items without a target need staff review.</p>
    <p className="muted mb-5 text-sm">The alert level decides when an item appears here; the target decides the replenishment quantity. Targets equal to the alert level leave stock at its alert boundary. Review quantities before ordering.</p>
    <div className="replenishment-actions mb-5 flex flex-wrap gap-3"><button className="btn" disabled={!snapshot} onClick={()=>window.print()}>Print replenishment list</button><button className="btn secondary" onClick={()=>{setSnapshot(null);setError("");setRetry(value=>value+1);}}>Refresh list</button></div>
    {error?<p role="alert" className="replenishment-actions mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error} Use Refresh list to retry.</p>:null}
    {!snapshot&&!error?<p role="status" className="replenishment-actions">Loading replenishment list…</p>:null}
    {snapshot?<>
      <p className="mb-4 text-sm">Snapshot refreshed {new Date(snapshot.refreshedAt).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",dateStyle:"medium",timeStyle:"medium"})} (Malaysia time). <span className="replenishment-actions">Refreshes every five seconds; pauses while printing.</span></p>
      <section className="panel"><h2 className="mb-4 text-xl font-semibold">{snapshot.items.length} items flagged · {total} units to replenish across items with targets</h2>
        <p className="muted mb-4 text-sm">{snapshot.items.filter(item=>item.target_stock===null).length} flagged items have no target; their quantities are excluded from the total. Set targets in Pharmacy stock.</p>
        {snapshot.items.length?<div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Current active stock requiring replenishment review</caption><thead><tr><th scope="col">Item</th><th scope="col">Status</th><th scope="col">Stock units</th><th scope="col">Alert level</th><th scope="col">Target stock</th><th scope="col">Units to replenish</th></tr></thead><tbody>{snapshot.items.map(item=><tr key={item.id}><th scope="row" className="break-words">{medicineLabel(item)}</th><td>{item.stock===0?"Out of stock":item.stock===item.low_stock_threshold?"At alert level":"Low stock"}</td><td>{item.stock}</td><td>{item.low_stock_threshold}</td><td>{item.target_stock??"Not set"}</td><td className="font-semibold">{item.target_stock===null?"Needs target":Math.max(0,item.target_stock-item.stock)}</td></tr>)}</tbody></table></div>:<p>No active items are at or below their alert level.</p>}
      </section>
      <p className="muted mt-5 text-sm">Planning list only. Printing does not place an order or change stock. Record delivered items through Receive stock in Pharmacy stock. Inactive items are excluded.</p>
    </>:<p className="replenishment-print-unavailable">Replenishment list unavailable. Load a current stock snapshot before printing.</p>}
  </main>;
}
