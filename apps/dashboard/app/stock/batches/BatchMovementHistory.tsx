"use client";
import {useEffect,useRef,useState} from "react";
import {BatchMovementHistory as History,DemoApi} from "@smart-skin/shared";
import BatchHistoryContent from "./BatchHistoryContent";
export default function BatchMovementHistory({api,medicineId,receiptId,onClose}:{api:DemoApi;medicineId:string;receiptId:string;onClose:()=>void}){
  const [data,setData]=useState<History|null>(null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  const heading=useRef<HTMLHeadingElement>(null);useEffect(()=>{heading.current?.focus();},[]);
  useEffect(()=>{let active=true,fetching=false;setData(null);setError("");async function load(){if(fetching)return;fetching=true;try{const result=await api.batchMovementHistory(medicineId,receiptId);if(active){setData(result);setError("");}}catch(e){if(active){setData(null);setError(e instanceof Error?e.message:"Cannot load batch history.");}}finally{fetching=false;}}void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};},[api,medicineId,receiptId,retry]);
  return <section className="panel mt-5" aria-label="Batch movement history"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">Batch movement history</h2><div className="my-4 flex flex-wrap gap-3"><button className="btn secondary" onClick={()=>setRetry(value=>value+1)}>Refresh batch history</button><button className="btn secondary" onClick={onClose}>Close batch history</button></div><p className="muted mb-3 text-sm">Refreshes every five seconds. Read-only history.</p>{error?<p role="alert" className="mb-4 text-red-800">{error} Use Refresh batch history to retry.</p>:null}{data?<BatchHistoryContent history={data}/>:!error?<p role="status">Loading batch history…</p>:null}</section>;
}
