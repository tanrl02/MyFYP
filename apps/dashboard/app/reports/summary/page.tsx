"use client";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,VisitSummary,VisitSummaryFilter} from "@smart-skin/shared";
import {VisitAnalysis,VisitStatusChart,VisitTrendChart,bucketLabel,statusColumns} from "./VisitCharts";

const months=Array.from({length:12},(_,index)=>new Date(Date.UTC(2000,index,1)).toLocaleDateString("en-GB",{month:"long",timeZone:"UTC"}));
export default function VisitSummaryPage(){
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo"),[]);
  const [filter,setFilter]=useState<VisitSummaryFilter>(()=>{const today=new Date(Date.now()+8*3600000);return {period:"month",year:today.getUTCFullYear(),month:today.getUTCMonth()+1};});
  const [period,setPeriod]=useState<VisitSummaryFilter["period"]>("month");
  const [report,setReport]=useState<VisitSummary|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true,fetching=false;setReport(null);setError("");setLoading(true);
    async function load(){if(fetching)return;fetching=true;try{const result=await api.visitSummary(filter);if(active){setReport(result);setError("");}}catch(e){if(active){setReport(null);setError(e instanceof Error?e.message:"Cannot load visit summary.");}}finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};
  },[api,filter,retry]);
  return <main className="mx-auto max-w-6xl px-5 py-8">
    <nav className="flex flex-wrap gap-5"><a className="underline" href="/feedback/analysis">Feedback analysis</a><a className="underline" href="/stock/reports">Inventory analysis</a><a className="underline" href="/reports">Daily clinic report</a><a className="underline" href="/reports/weekly">Weekly visits</a></nav>
    <div className="my-6 flex flex-wrap justify-between gap-3"><h1 className="text-3xl font-semibold">Visit summary & analysis</h1><span className="badge">Staff Demo · synthetic data</span></div>
    <section className="panel mb-5"><form className="flex flex-wrap items-end gap-4" onSubmit={e=>{
      e.preventDefault();const values=new FormData(e.currentTarget),year=Number(values.get("year"));
      setFilter(period==="month"?{period,year,month:Number(values.get("month"))}:period==="quarter"?{period,year,quarter:Number(values.get("quarter"))}:{period,year});setRetry(n=>n+1);
    }}>
      <label className="font-semibold">Period<select aria-label="Report period" name="period" value={period} onChange={e=>setPeriod(e.target.value as typeof period)} className="mt-2 block rounded-lg border p-3"><option value="month">Monthly</option><option value="quarter">Quarterly</option><option value="year">Yearly</option></select></label>
      <label className="font-semibold">Year<input aria-label="Report year" name="year" type="number" min="2" max="9998" step="1" required defaultValue={filter.year} className="mt-2 block w-32 rounded-lg border p-3"/></label>
      {period==="month"?<label className="font-semibold">Month<select aria-label="Report month" name="month" defaultValue={filter.period==="month"?filter.month:1} className="mt-2 block rounded-lg border p-3">{months.map((month,index)=><option key={month} value={index+1}>{month}</option>)}</select></label>:null}
      {period==="quarter"?<label className="font-semibold">Quarter<select aria-label="Report quarter" name="quarter" defaultValue="1" className="mt-2 block rounded-lg border p-3"><option value="1">Q1 · Jan–Mar</option><option value="2">Q2 · Apr–Jun</option><option value="3">Q3 · Jul–Sep</option><option value="4">Q4 · Oct–Dec</option></select></label>:null}
      <button type="submit" className="btn">View summary</button>
    </form><p className="muted mt-3 text-sm">Calendar periods in Malaysia time (UTC+8). Choose your filters and select View summary. Counts refresh every ten seconds.</p></section>
    {error?<div role="alert" className="panel mb-5 text-red-800">{error}<button className="btn secondary ml-3" onClick={()=>setRetry(n=>n+1)}>Retry summary</button></div>:null}
    {loading?<p role="status">Loading visit summary…</p>:null}
    {report?<>
      <h2 className="mb-2 text-2xl font-semibold">{report.period==="month"?"Monthly":report.period==="quarter"?"Quarterly":"Yearly"} summary · {bucketLabel(report.start_date,"day")} – {bucketLabel(report.end_date,"day")}</h2>
      <p className="muted mb-5 text-sm">Scheduled appointment records, including future appointments. Rescheduled originals are counted separately from cancellations. These counts are not unique patient counts.</p>
      <section aria-label="Period totals" className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[["Booking records",report.visits.total],["Completed",report.visits.completed],["Missed",report.visits.missed],["Waiting or called",report.visits.waiting+report.visits.called]].map(([label,value])=><div className="panel" key={label}><p className="muted">{label}</p><strong className="mt-2 block text-3xl">{value}</strong></div>)}</section>
      <VisitAnalysis report={report}/>
      <div className="mb-5 grid items-start gap-5 lg:grid-cols-[2fr_1fr]"><VisitTrendChart report={report}/><VisitStatusChart report={report}/></div>
      <section className="panel"><h2 className="text-xl font-semibold">Detailed counts by {report.granularity}</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Scheduled records and current statuses</caption><thead><tr><th scope="col">{report.granularity==="day"?"Appointment date":"Appointment month"}</th><th scope="col">Total</th>{statusColumns.map(([key,label])=><th scope="col" key={key}>{label}</th>)}</tr></thead><tbody>{report.buckets.map(row=><tr key={row.start_date}><th scope="row">{bucketLabel(row.start_date,report.granularity)}</th><td>{row.visits.total}</td>{statusColumns.map(([key])=><td key={key}>{row.visits[key]}</td>)}</tr>)}</tbody><tfoot><tr className="font-semibold"><th scope="row">Period total</th><td>{report.visits.total}</td>{statusColumns.map(([key])=><td key={key}>{report.visits[key]}</td>)}</tr></tfoot></table></div></section>
      <p className="muted mt-5 text-sm">Updated {new Date(report.generated_at).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",dateStyle:"medium",timeStyle:"medium"})} (Malaysia time). Synthetic records only.</p>
    </>:null}
  </main>;
}
