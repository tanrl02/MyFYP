"use client";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,UsableStockAlerts,medicineLabel} from "@smart-skin/shared";

export default function UsableStockAlertsPage(){
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo"),[]);
  const [data,setData]=useState<UsableStockAlerts|null>(null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true,fetching=false;setData(null);setError("");async function load(){if(fetching)return;fetching=true;try{const result=await api.usableStockAlerts();if(active){setData(result);setError("");}}catch(e){if(active){setData(null);setError(e instanceof Error?e.message:"Cannot load usable-stock alerts.");}}finally{fetching=false;}}void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};},[api,retry]);
  return <main className="mx-auto max-w-6xl px-5 py-8"><nav className="flex flex-wrap gap-5"><a className="underline" href="/stock">← Pharmacy stock</a><a className="underline" href="/stock/batches">Batch stock overview</a><a className="underline" href="/stock/replenishment">Physical-stock replenishment</a></nav>
    <h1 className="my-6 text-3xl font-semibold">Low usable-stock alerts</h1><p className="mb-3">Staff Demo · synthetic items. Active items whose usable tracked units are at or below their saved alert level.</p>
    <p className="muted mb-5 text-sm">Usable tracked stock excludes expired and held batches. Untracked stock is shown separately because its physical batch and expiry need checking. An alert does not mean there is no physical stock or automatically recommend an order.</p>
    <button className="btn secondary mb-5" onClick={()=>setRetry(value=>value+1)}>Refresh usable-stock alerts</button>
    {error?<p role="alert" className="panel mb-5 text-red-800">{error} Use Refresh usable-stock alerts to retry.</p>:null}
    {!data&&!error?<p role="status">Loading usable-stock alerts…</p>:null}
    {data?<><p className="muted mb-4 text-sm">As of {data.as_of} (Malaysia time) · {data.active_items} active items checked · refreshes every five seconds.</p>
      <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-4">{[["Items flagged",data.alerts.length],["No usable tracked stock",data.no_usable_items],["Low usable tracked stock",data.low_usable_items],["Untracked stock to review",data.untracked_review_items]].map(([label,value])=><section className="panel" key={label}><h2 className="text-sm font-semibold">{label}</h2><strong className="mt-2 block text-3xl">{value}</strong></section>)}</div>
      <section className="panel"><h2 className="text-xl font-semibold">Items needing review</h2><p className="muted my-3 text-sm">No usable means zero; low usable means a positive quantity at or below the alert level. Blocked tracked units are expired or held, counted once even if both apply. Review untracked stock before ordering supplies.</p>
      {data.alerts.length?<div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Active medicine usable stock and separate untracked quantities</caption><thead><tr><th scope="col">Item</th><th scope="col">Usable tracked</th><th scope="col">Alert level</th><th scope="col">Physical stock</th><th scope="col">Blocked tracked</th><th scope="col">Untracked to review</th><th scope="col">Details</th></tr></thead><tbody>{data.alerts.map(item=><tr key={item.medicine_id}><th scope="row" className="break-words">{medicineLabel(item)}<span className="mt-1 block text-xs normal-case">{item.usable_units===0?"No usable tracked stock":"Low usable tracked stock"}</span></th><td className="font-semibold text-amber-900">{item.usable_units}</td><td>{item.low_stock_threshold}</td><td>{item.stock}</td><td>{item.blocked_tracked_units}</td><td>{item.untracked_units}</td><td><a className="underline" href={`/stock/batches?medicine=${encodeURIComponent(item.medicine_id)}`}>View batch stock</a></td></tr>)}</tbody></table></div>:<p>No active items have usable tracked stock at or below their alert level.</p>}
      </section></>:null}
  </main>;
}
