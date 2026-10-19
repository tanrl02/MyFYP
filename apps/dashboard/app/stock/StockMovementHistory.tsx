"use client";
import {useEffect,useState} from "react";
import {DemoApi,Medicine,StockMovementHistory as History,medicineLabel,visitTime} from "@smart-skin/shared";
const movementNames={received:"Received",dispensed:"Dispensed",damaged:"Damaged",lost:"Lost"};
export default function StockMovementHistory({api,medicines}:{api:DemoApi;medicines:Medicine[]}){
  const [item,setItem]=useState(""),[history,setHistory]=useState<History|null>(null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  const [cursor,setCursor]=useState<string|null>(null),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let active=true,fetching=false;
    if(!cursor)setHistory(null);
    setError("");setBusy(false);
    if(!item)return;
    async function load(){
      if(fetching)return;fetching=true;setBusy(true);
      try{
        const saved=await api.stockMovements(item,cursor??undefined);
        if(active){setHistory(previous=>{
          if(!cursor||!previous)return saved;
          const seen=new Set(previous.movements.map(m=>`${m.kind}:${m.source_id}`));
          return {...saved,movements:[...previous.movements,...saved.movements.filter(m=>!seen.has(`${m.kind}:${m.source_id}`))]};
        });setError("");}
      }catch(e){if(active)setError(e instanceof Error?e.message:"Cannot load movement history.");}
      finally{fetching=false;if(active)setBusy(false);}
    }
    void load();
    const timer=cursor?undefined:setInterval(load,5000);
    return()=>{active=false;if(timer)clearInterval(timer);};
  },[api,item,cursor,retry]);
  return <section className="panel mb-6" aria-label="Medicine movement history"><h2 className="text-lg font-semibold">Medicine movement history</h2><p className="muted my-3 text-sm">Receipts, completed dispensing and damaged/lost deductions, newest first. Select from the full catalogue, including inactive items. Recent history refreshes every five seconds. Loading older movements pauses refresh until you choose Refresh newest.</p><label>History medicine<select value={item} onChange={e=>{setItem(e.target.value);setCursor(null);setHistory(null);setError("");}}><option value="">Choose item</option>{medicines.map(m=><option key={m.id} value={m.id}>{medicineLabel(m)}{m.active?"":" · Inactive"}</option>)}</select></label>{error?<p role="alert" className="my-3 text-red-800">{error}<button className="btn secondary ml-3" disabled={busy} onClick={()=>setRetry(n=>n+1)}>Retry history</button></p>:null}{!item?<p className="muted mt-3">Choose a medicine to view saved movements.</p>:!history&&!error?<p className="mt-3">Loading movement history…</p>:null}{history?<><h3 className="mt-4 font-semibold">{medicineLabel(history.medicine)}</h3><p className="my-3">Stock at last history update: {history.medicine.stock} units · {history.medicine.active?"Active":"Inactive"}</p><p className="muted my-3 text-sm">Showing {history.movements.length} saved movements{history.has_more?"; older records exist":""}. Initial stock is not listed as a movement. Before/after balances were not saved for dispensing, so this list is not a running balance. Receipt labels use the current catalogue; dispensing and loss labels use their saved details.</p>{history.movements.length?history.movements.map(m=><article className="border-t py-4" key={`${m.kind}-${m.source_id}`}><div className="flex flex-wrap justify-between gap-2"><strong>{movementNames[m.kind]} · {m.change>0?"+":""}{m.change} units</strong><span>{visitTime(m.created_at)}</span></div>{m.item_label?<p className="my-2">{m.item_label}</p>:null}{m.reason?<p className="my-2 whitespace-pre-wrap break-words">{m.reason}</p>:null}<p className="muted my-2 text-sm">{m.stock_before!==null&&m.stock_after!==null?`Stock at recording: ${m.stock_before} → ${m.stock_after}`:"Stock before/after was not saved for this dispensing."}</p><p className="muted text-xs">{m.actor_id?`${m.actor_id} · `:""}{movementNames[m.kind]} record {m.source_id.slice(0,8)}</p></article>):<p>No saved movements for this medicine.</p>}<div className="mt-4 flex flex-wrap gap-3">{history.next_cursor?<button className="btn" disabled={busy} onClick={()=>setCursor(history.next_cursor)}>{busy?"Loading…":"Load older movements"}</button>:<p className="muted text-sm">All saved movements loaded.</p>}<button className="btn secondary" disabled={busy} onClick={()=>{setCursor(null);setRetry(n=>n+1);}}>Refresh newest</button></div>{cursor?<p role="status" className="muted mt-3 text-sm">History refresh paused while browsing older movements. Refresh newest returns to the latest 100.</p>:null}</>:null}</section>;
}
