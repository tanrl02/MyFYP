"use client";
import {useStaffIdentity} from "../../StaffIdentity";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,StockExpiry,medicineLabel,visitTime} from "@smart-skin/shared";

export default function StockExpiryPage(){
  const {actor:staffActor,names:staffNames}=useStaffIdentity();
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000",staffActor),[staffActor]);
  const [data,setData]=useState<StockExpiry|null>(null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true,fetching=false;async function load(){if(fetching)return;fetching=true;try{const result=await api.stockExpiry();if(active){setData(result);setError("");}}catch(e){if(active){setData(null);setError(e instanceof Error?e.message:"Cannot load expiry review.");}}finally{fetching=false;}}void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};},[api,retry]);
  return <main className="mx-auto max-w-6xl px-5 py-8"><nav className="flex flex-wrap gap-5"><a className="underline" href="/stock">← Pharmacy stock</a><a className="underline" href="/stock/batches">Batch stock overview</a><a className="underline" href="/stock/reports">Inventory analysis</a></nav>
    <h1 className="my-6 text-3xl font-semibold">Received-batch expiry review</h1><p className="mb-3">{staffNames[staffActor]||staffActor} · synthetic items. Expired dates and dates due within 30 days, including today, use Malaysia time.</p>
    <p className="muted mb-5 text-sm">These are receiving records, including inactive catalogue items. New tracked batches show remaining units after dispensing and linked losses; depleted tracked batches are excluded. Older receipts remain untracked and need a physical stock check. This review does not change stock.</p>
    <button className="btn secondary mb-5" onClick={()=>{setData(null);setError("");setRetry(value=>value+1);}}>Refresh expiry review</button>
    {error?<p role="alert" className="panel mb-5 text-red-800">{error} Use Refresh expiry review to retry.</p>:null}
    {!data&&!error?<p role="status">Loading expiry review…</p>:null}
    {data?<><p className="mb-4 text-sm">As of {data.as_of} · upcoming window through {data.through_date} · Malaysia time. Refreshes every ten seconds.</p>
      <div className="mb-5 grid gap-4 md:grid-cols-3">{[["Expired receipt records",data.expired_receipts],["Due today–30 days",data.due_soon_receipts],["Receipts without batch expiry",data.untracked_receipts]].map(([label,value])=><section className="panel" key={label}><h2 className="font-semibold">{label}</h2><strong className="mt-2 block text-3xl">{value}</strong></section>)}</div>
      <section className="panel"><h2 className="text-xl font-semibold">Batch records to review</h2><p className="muted my-3 text-sm">Earliest expiry first. Each delivery is a separate receipt; the same batch can appear more than once. {data.has_more?"Showing the first 200 records; totals include all matching records.":`${data.items.length} matching records.`}</p>
        {data.items.length?<div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Received batch expiry dates and original received quantities</caption><thead><tr><th scope="col">Item</th><th scope="col">Batch</th><th scope="col">Expiry</th><th scope="col">Status</th><th scope="col">Originally received</th><th scope="col">Remaining units</th><th scope="col">Received at</th></tr></thead><tbody>{data.items.map(item=><tr key={item.id}><th scope="row" className="break-words">{medicineLabel(item)}{item.active?null:<span className="block">Inactive catalogue item</span>}</th><td className="break-all">{item.batch_number}</td><td>{item.expiry_date}</td><td className={item.days_to_expiry<0?"font-semibold text-red-800":"font-semibold text-amber-800"}>{item.days_to_expiry<0?`Expired ${-item.days_to_expiry} days ago`:item.days_to_expiry===0?"Expires today":`In ${item.days_to_expiry} days`}</td><td>{item.quantity} units</td><td>{item.remaining_units??"Untracked"}</td><td>{visitTime(item.created_at)}</td></tr>)}</tbody></table></div>:<p>No receiving records have expiry dates in this window. Older records without expiry details are counted separately.</p>}
      </section></>:null}
  </main>;
}
