"use client";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,FeedbackSummary,ReportPeriodFilter} from "@smart-skin/shared";

const months=Array.from({length:12},(_,i)=>new Date(Date.UTC(2000,i,1)).toLocaleDateString("en-GB",{month:"long",timeZone:"UTC"}));
export default function FeedbackAnalysisPage(){
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo"),[]);
  const [filter,setFilter]=useState<ReportPeriodFilter>(()=>{const now=new Date(Date.now()+8*3600000);return {period:"month",year:now.getUTCFullYear(),month:now.getUTCMonth()+1};});
  const [period,setPeriod]=useState<ReportPeriodFilter["period"]>("month");
  const [report,setReport]=useState<FeedbackSummary|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true,fetching=false;setReport(null);setError("");setLoading(true);
    async function load(){if(fetching)return;fetching=true;try{const data=await api.feedbackSummary(filter);if(active){setReport(data);setError("");}}catch(e){if(active){setReport(null);setError(e instanceof Error?e.message:"Cannot load feedback analysis.");}}finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};
  },[api,filter,retry]);
  return <main className={`feedback-print ${report&&!loading&&!error?"feedback-ready":""} mx-auto max-w-5xl px-5 py-8`}>
    <nav className="feedback-actions flex flex-wrap gap-5"><a className="underline" href="/feedback">Visit feedback</a><a className="underline" href="/reports/summary">Visit analysis</a><a className="underline" href="/reports">Daily clinic report</a></nav>
    <header className="feedback-header my-6 flex flex-wrap justify-between gap-3"><h1 className="text-3xl font-semibold">Feedback analysis</h1><span className="badge">Staff Demo · synthetic data</span></header>
    <p className="feedback-print-unavailable">Feedback analysis is unavailable. Load a report successfully before printing.</p>
    <section className="feedback-actions panel mb-5"><form className="flex flex-wrap items-end gap-4" onSubmit={e=>{
      e.preventDefault();const data=new FormData(e.currentTarget),year=Number(data.get("year"));
      setFilter(period==="month"?{period,year,month:Number(data.get("month"))}:period==="quarter"?{period,year,quarter:Number(data.get("quarter"))}:{period,year});setRetry(n=>n+1);
    }}>
      <label className="font-semibold">Period<select aria-label="Report period" value={period} onChange={e=>setPeriod(e.target.value as typeof period)} className="mt-2 block rounded-lg border p-3"><option value="month">Monthly</option><option value="quarter">Quarterly</option><option value="year">Yearly</option></select></label>
      <label className="font-semibold">Year<input aria-label="Report year" name="year" type="number" min="2" max="9998" step="1" required defaultValue={filter.year} className="mt-2 block w-32 rounded-lg border p-3"/></label>
      {period==="month"?<label className="font-semibold">Month<select aria-label="Report month" name="month" defaultValue={filter.period==="month"?filter.month:1} className="mt-2 block rounded-lg border p-3">{months.map((name,i)=><option key={name} value={i+1}>{name}</option>)}</select></label>:null}
      {period==="quarter"?<label className="font-semibold">Quarter<select aria-label="Report quarter" name="quarter" defaultValue="1" className="mt-2 block rounded-lg border p-3">{[1,2,3,4].map(q=><option key={q} value={q}>Q{q} · {months[(q-1)*3]}–{months[q*3-1]}</option>)}</select></label>:null}
      <button type="submit" className="btn">View analysis</button>
    </form><button type="button" className="btn secondary mt-4" disabled={loading||!!error||!report} onClick={()=>window.print()}>Print feedback analysis</button><p className="muted mt-2 text-sm">Prints the displayed ratings and chart with the period and update time. Choose Save as PDF in your browser’s print dialog if available.</p><p className="muted mt-3 text-sm">Calendar periods by original feedback submission date in Malaysia time (UTC+8). Refreshes every ten seconds.</p></section>
    {error?<div role="alert" className="panel mb-5 text-red-800">{error}<button className="btn secondary ml-3" onClick={()=>setRetry(n=>n+1)}>Retry analysis</button></div>:null}
    {loading?<p role="status">Loading feedback analysis…</p>:null}
    {report?<>
      <h2 className="mb-4 text-xl font-semibold">{report.period==="month"?"Monthly":report.period==="quarter"?"Quarterly":"Yearly"} summary · {report.start_date} – {report.end_date}</h2>
      <section aria-label="Feedback totals" className="feedback-totals mb-5 grid gap-4 sm:grid-cols-2"><div className="panel"><p className="muted">Submitted ratings</p><strong className="mt-2 block text-3xl">{report.count}</strong></div><div className="panel"><p className="muted">Average rating</p><strong className="mt-2 block text-3xl">{report.average_rating===null?"No ratings":`${report.average_rating.toFixed(2)} / 5`}</strong></div></section>
      <section className="feedback-chart panel"><h2 className="text-xl font-semibold">Rating distribution</h2><p className="muted mt-2 mb-5">Each bar shows its share of all submitted ratings in this period.</p>
        {!report.count?<p className="mb-5">No feedback was submitted in this period.</p>:null}
        {report.ratings.map(row=><div className="mb-4" key={row.rating}><div className="mb-1 flex justify-between gap-3"><span>{row.rating} {row.rating===1?"star":"stars"}</span><span>{row.count} · {report.count?(row.count/report.count*100).toFixed(1):"0.0"}%</span></div><div aria-hidden="true" className="h-5 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-emerald-700" style={{width:`${report.count?row.count/report.count*100:0}%`}}/></div></div>)}
      </section>
      <p className="muted mt-5 text-sm">Uses all submissions in this period, beyond the latest 100 list. Edited feedback contributes its current rating once under its original submission date. These are submitted opinions, not a response rate or clinical outcome measure.</p>
      <p className="muted mt-3 text-sm">Updated {new Date(report.generated_at).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",dateStyle:"medium",timeStyle:"medium"})} (Malaysia time). Synthetic records only.</p>
    </>:null}
  </main>;
}
