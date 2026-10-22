"use client";
import {useEffect,useMemo,useState} from "react";
import BatchHoldForm from "./BatchHoldForm";
import BatchMovementHistory from "./BatchMovementHistory";
import {BatchStockOverview,DemoApi,Medicine,medicineLabel} from "@smart-skin/shared";

export default function BatchStockPage(){
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo"),[]);
  const [holdBatch,setHoldBatch]=useState<BatchStockOverview["batches"][number]|null>(null),[holdBusy,setHoldBusy]=useState(false);
  const [historyReceipt,setHistoryReceipt]=useState("");
  const [medicines,setMedicines]=useState<Medicine[]>([]),[item,setItem]=useState(""),[data,setData]=useState<BatchStockOverview|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true,fetching=false;setData(null);setError("");setLoading(true);
    async function load(){if(fetching)return;fetching=true;try{
      const [catalogue,overview]=await Promise.all([api.medicines(),item?api.batchStockOverview(item):Promise.resolve(null)]);
      if(active){setMedicines(catalogue);setData(overview);setError("");}
    }catch(e){if(active){setData(null);setError(e instanceof Error?e.message:"Cannot load batch stock.");}}finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};
  },[api,item,retry]);
  useEffect(()=>{const selected=new URLSearchParams(window.location.search).get("medicine");if(selected)setItem(selected);},[]);
  const tracked=data?.batches.reduce((total,batch)=>total+batch.remaining_units,0)??0;
  const expired=data?.batches.reduce((total,batch)=>total+(batch.expired?batch.remaining_units:0),0)??0;
  const usable=data?.batches.reduce((total,batch)=>total+(!batch.expired&&!batch.held?batch.remaining_units:0),0)??0;
  return <main className="mx-auto max-w-6xl px-5 py-8"><nav className="flex flex-wrap gap-5"><a className="underline" href="/stock">← Pharmacy stock</a><a className="underline" href="/stock/usable-alerts">Low usable-stock alerts</a><a className="underline" href="/stock/expiry">Batch expiry review</a><a className="underline" href="/care">Dispensing & billing</a></nav>
    <h1 className="my-6 text-3xl font-semibold">Batch stock overview</h1><p className="mb-4">Staff Demo · synthetic items. Select a medicine to see tracked batches and its separate untracked stock.</p>
    <section className="panel mb-5"><label className="block font-semibold">Medicine<select disabled={holdBusy} aria-label="Batch overview medicine" className="mt-2" value={item} onChange={e=>{setData(null);setError("");setLoading(true);setHistoryReceipt("");setHoldBatch(null);setItem(e.target.value);}}><option value="">Choose a medicine</option>{medicines.map(medicine=><option value={medicine.id} key={medicine.id}>{medicineLabel(medicine)}{medicine.active?"":" · Inactive"}</option>)}</select></label><button className="btn secondary mt-4" disabled={holdBusy} onClick={()=>setRetry(value=>value+1)}>Refresh batch stock</button><p className="muted mt-3 text-sm">Refreshes every five seconds. Inactive catalogue items are included.</p></section>
    {error?<p role="alert" className="panel mb-5 text-red-800">{error} Use Refresh batch stock to retry.</p>:null}
    {loading?<p role="status">Loading batch stock…</p>:null}
    {!loading&&!error&&!item?<p>Choose a medicine to view its batch stock.</p>:null}
    {data?<><section className="panel mb-5"><h2 className="text-xl font-semibold">{medicineLabel(data.medicine)}</h2><p className="muted my-3 text-sm">{data.medicine.active?"Active catalogue item":"Inactive catalogue item"} · Expiry status as of {data.as_of} (Malaysia time). Batches expiring today remain usable through today.</p>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{[["Total physical units",data.stock],["Tracked units",tracked],["Untracked units",data.untracked_units],["Expired tracked units",expired]].map(([label,value])=><div key={label}><p className="muted text-sm">{label}</p><strong className="mt-2 block text-3xl">{value}</strong></div>)}</div>
      <section aria-label="Usable tracked stock" className="mt-5 rounded-xl border border-[#ccdcd4] bg-[#f4f7f6] p-4"><h3 className="font-semibold">Usable tracked units</h3><strong className="mt-2 block text-3xl">{usable}</strong><p className="muted mt-2 text-sm">Remaining units in tracked batches that are neither expired nor on hold. Untracked stock is excluded because its physical expiry needs checking. Dispensing rechecks the latest source quantities and status.</p>{usable===0?<p className="mt-3 text-sm">No usable tracked stock for this medicine. Review untracked stock physically or receive a suitable batch before choosing a dispensing source.</p>:null}</section>
      <p className="muted mt-4 text-sm">Total physical stock includes expired stock. Expired and held tracked units cannot be dispensed. Held units stay part of tracked physical stock. Untracked stock includes older receipts and receipts without batch details; verify physical batch and expiry before use.</p></section>
      <section className="panel"><h2 className="text-xl font-semibold">Tracked receipt batches</h2><p className="muted my-3 text-sm">Earliest expiry first. Each receipt is separate, even when batch numbers match. Live balances include dispensing and batch-linked losses. Depleted batches stay visible here for reference.</p>
      {data.batches.length?<div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Tracked batches and their current remaining quantities</caption><thead><tr><th scope="col">Batch</th><th scope="col">Expiry date</th><th scope="col">Remaining units</th><th scope="col">Status</th><th scope="col">Receipt</th><th scope="col">Actions</th></tr></thead><tbody>{data.batches.map(batch=><tr key={batch.receipt_id}><th scope="row" className="break-all">{batch.batch_number}</th><td>{batch.expiry_date}</td><td className="font-semibold">{batch.remaining_units}</td><td className={batch.held||batch.expired&&batch.remaining_units>0?"font-semibold text-red-800":""}>{batch.held?"On hold · blocked":batch.remaining_units===0?"Depleted":batch.expired?"Expired · blocked":batch.expiry_date===data.as_of?"Expires today":"Available"}</td><td className="break-all">{batch.receipt_id}</td><td><button className="btn secondary" disabled={holdBusy} aria-label={`View history for batch ${batch.batch_number}, receipt ${batch.receipt_id}`} onClick={()=>setHistoryReceipt(batch.receipt_id)}>View history</button><button className="btn secondary mt-2" disabled={holdBusy} aria-label={`${batch.held?"Release hold":"Hold batch"} ${batch.batch_number}, receipt ${batch.receipt_id}`} onClick={()=>setHoldBatch(batch)}>{batch.held?"Release hold":"Hold batch"}</button>{batch.held?<p className="mt-2 whitespace-pre-wrap break-words text-sm">{batch.hold_reason}</p>:null}</td></tr>)}</tbody></table></div>:<p>No tracked batch balances for this medicine. Its stock is shown separately as untracked.</p>}
      </section>{holdBatch?<BatchHoldForm key={`${item}-${holdBatch.receipt_id}-${holdBatch.held}`} api={api} medicineId={item} batch={holdBatch} onBusyChange={setHoldBusy} onSaved={()=>{setHoldBatch(null);setRetry(value=>value+1);}} onClose={()=>setHoldBatch(null)}/>:null}{historyReceipt?<BatchMovementHistory key={`${item}-${historyReceipt}`} api={api} medicineId={item} receiptId={historyReceipt} onClose={()=>setHistoryReceipt("")}/>:null}</>:null}
  </main>;
}
