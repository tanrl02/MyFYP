"use client";
import {useStaffIdentity} from "../../StaffIdentity";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,BillingSummary,ReportPeriodFilter,money} from "@smart-skin/shared";
import {downloadBillingReport} from "./billingReportCsv";

const months=Array.from({length:12},(_,i)=>new Date(Date.UTC(2000,i,1)).toLocaleDateString("en-GB",{month:"long",timeZone:"UTC"}));
export default function BillingAnalysisPage(){
  const {actor:staffActor,names:staffNames}=useStaffIdentity();
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000",staffActor),[staffActor]);
  const [filter,setFilter]=useState<ReportPeriodFilter>(()=>{const now=new Date(Date.now()+8*3600000);return {period:"month",year:now.getUTCFullYear(),month:now.getUTCMonth()+1};});
  const [period,setPeriod]=useState<ReportPeriodFilter["period"]>("month");
  const [report,setReport]=useState<BillingSummary|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true,fetching=false;setReport(null);setError("");setLoading(true);
    async function load(){if(fetching)return;fetching=true;try{const data=await api.billingSummary(filter);if(active){setReport(data);setError("");}}catch(e){if(active){setReport(null);setError(e instanceof Error?e.message:"Cannot load billing analysis.");}}finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};
  },[api,filter,retry]);
  return <main className={`billing-print ${report&&!loading&&!error?"billing-ready":""} mx-auto max-w-5xl px-5 py-8`}>
    <nav className="billing-actions flex flex-wrap gap-5"><a className="underline" href="/care">Care & bills</a><a className="underline" href="/reports/summary">Visit analysis</a><a className="underline" href="/reports">Daily clinic report</a></nav>
    <header className="billing-header my-6 flex flex-wrap justify-between gap-3"><h1 className="text-3xl font-semibold">Billing analysis</h1><span className="badge">{staffNames[staffActor]||staffActor} · synthetic data</span></header>
    <p className="billing-print-unavailable">Billing analysis is unavailable. Load a report successfully before printing.</p>
    <section className="billing-actions panel mb-5"><form className="flex flex-wrap items-end gap-4" onSubmit={e=>{
      e.preventDefault();const data=new FormData(e.currentTarget),year=Number(data.get("year"));
      setFilter(period==="month"?{period,year,month:Number(data.get("month"))}:period==="quarter"?{period,year,quarter:Number(data.get("quarter"))}:{period,year});setRetry(n=>n+1);
    }}>
      <label className="font-semibold">Period<select aria-label="Report period" value={period} onChange={e=>setPeriod(e.target.value as typeof period)} className="mt-2 block rounded-lg border p-3"><option value="month">Monthly</option><option value="quarter">Quarterly</option><option value="year">Yearly</option></select></label>
      <label className="font-semibold">Year<input aria-label="Report year" name="year" type="number" min="2" max="9998" step="1" required defaultValue={filter.year} className="mt-2 block w-32 rounded-lg border p-3"/></label>
      {period==="month"?<label className="font-semibold">Month<select aria-label="Report month" name="month" defaultValue={filter.period==="month"?filter.month:1} className="mt-2 block rounded-lg border p-3">{months.map((name,i)=><option key={name} value={i+1}>{name}</option>)}</select></label>:null}
      {period==="quarter"?<label className="font-semibold">Quarter<select aria-label="Report quarter" name="quarter" defaultValue="1" className="mt-2 block rounded-lg border p-3">{[1,2,3,4].map(q=><option key={q} value={q}>Q{q} · {months[(q-1)*3]}–{months[q*3-1]}</option>)}</select></label>:null}
      <button type="submit" className="btn">View analysis</button>
    </form><button type="button" className="btn secondary mt-4" disabled={loading||!!error||!report} onClick={()=>window.print()}>Print billing analysis</button><button type="button" className="btn secondary ml-3 mt-4" disabled={loading||!!error||!report} onClick={()=>{if(report)downloadBillingReport(report);}}>Download billing CSV</button><p className="muted mt-2 text-sm">Prints the displayed summary, chart and breakdown, including its period and update time. Choose Save as PDF in your browser’s print dialog if available.</p><p className="muted mt-3 text-sm">CSV downloads the displayed totals and breakdown with the period, update time and simulation labels. Calendar periods by invoice issue date in Malaysia time (UTC+8). Refreshes every ten seconds.</p></section>
    {error?<div role="alert" className="panel mb-5 text-red-800">{error}<button className="btn secondary ml-3" onClick={()=>setRetry(n=>n+1)}>Retry analysis</button></div>:null}
    {loading?<p role="status">Loading billing analysis…</p>:null}
    {report?<>
      <h2 className="mb-4 text-xl font-semibold">{report.period==="month"?"Monthly":report.period==="quarter"?"Quarterly":"Yearly"} summary · {report.start_date} – {report.end_date}</h2>
      <section aria-label="Billing totals" className="billing-totals mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[["Invoices issued",report.billing.invoice_count],["Total billed",money(report.billing.billed_cents)],["Paid · simulation",money(report.billing.paid_cents)],["Outstanding",money(report.billing.unpaid_cents)]].map(([label,value])=><div key={label} className="panel"><p className="muted">{label}</p><strong className="mt-2 block text-2xl">{value}</strong></div>)}</section>
      <section className="billing-chart panel mb-5"><h2 className="text-xl font-semibold">Billed, paid and outstanding</h2><p className="muted mt-2 mb-5">Paid and outstanding amounts together make up the total billed for these invoices. All bars use the same scale.</p>
        {!report.billing.invoice_count?<p className="mb-5">No invoices were issued in this period.</p>:!report.billing.billed_cents?<p className="mb-5">These invoices have a zero total.</p>:null}
        {([['billed_cents','Total billed','bg-slate-600'],['paid_cents','Paid · simulation','bg-emerald-700'],['unpaid_cents','Outstanding','bg-amber-600']] as const).map(([key,label,color])=><div key={key} className="mb-4"><div className="mb-1 flex justify-between gap-3"><span>{label}</span><span>{money(report.billing[key])}</span></div><div aria-hidden="true" className="h-5 overflow-hidden rounded bg-slate-100"><div className={`h-full rounded ${color}`} style={{width:`${report.billing.billed_cents?report.billing[key]/report.billing.billed_cents*100:0}%`}}/></div></div>)}
        <p className="muted mt-4">{report.billing.paid_invoice_count} paid · {report.billing.unpaid_invoice_count} unpaid invoices. Each invoice is counted once.</p>
      </section>
      <section className="billing-breakdown panel"><h2 className="text-xl font-semibold">Breakdown by invoice issue {report.granularity==="day"?"date":"month"}</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Invoice issue cohorts and current simulated payment status in MYR</caption><thead><tr><th scope="col">{report.granularity==="day"?"Issue date":"Issue month"}</th><th scope="col">Invoices</th><th scope="col">Billed</th><th scope="col">Paid · simulation</th><th scope="col">Outstanding</th></tr></thead><tbody>{report.buckets.map(row=><tr key={row.start_date}><th scope="row">{report.granularity==="day"?row.start_date:row.start_date.slice(0,7)}</th><td>{row.billing.invoice_count}</td><td>{money(row.billing.billed_cents)}</td><td>{money(row.billing.paid_cents)}</td><td>{money(row.billing.unpaid_cents)}</td></tr>)}</tbody><tfoot><tr className="font-semibold"><th scope="row">Period total</th><td>{report.billing.invoice_count}</td><td>{money(report.billing.billed_cents)}</td><td>{money(report.billing.paid_cents)}</td><td>{money(report.billing.unpaid_cents)}</td></tr></tfoot></table></div></section>
      <p className="muted mt-5 text-sm">Grouped by invoice issue date, not appointment or payment date. Paid amounts reflect current simulated payment status, including payments made after the selected period. They are not cash collected during this period. Outstanding covers only invoices issued in this period, not all clinic debt. No real payments.</p>
      <p className="muted mt-3 text-sm">Updated {new Date(report.generated_at).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",dateStyle:"medium",timeStyle:"medium"})} (Malaysia time). Synthetic records only.</p>
    </>:null}
  </main>;
}
