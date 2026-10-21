"use client";
import {useEffect,useMemo,useState} from "react";
import {DemoApi,WeeklyVisitReport} from "@smart-skin/shared";

const columns=[["total","Total records"],["waiting","Waiting"],["called","Called"],["completed","Completed"],["cancelled","Cancelled"],["missed","Missed"],["rescheduled","Rescheduled"]] as const;
const dayLabel=(day:string)=>new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB",{weekday:"short",day:"numeric",month:"short",year:"numeric",timeZone:"UTC"});

export default function WeeklyReportsPage(){
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo"),[]);
  const [weekOf,setWeekOf]=useState(()=>new Date(Date.now()+8*3600000).toISOString().slice(0,10));
  const [report,setReport]=useState<WeeklyVisitReport|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true,fetching=false;
    setReport(null);setError("");setLoading(true);
    async function load(){
      if(fetching)return;fetching=true;
      try{const result=await api.weeklyReport(weekOf);if(active){setReport(result);setError("");}}
      catch(e){if(active){setReport(null);setError(e instanceof Error?e.message:"Cannot load weekly report.");}}
      finally{fetching=false;if(active)setLoading(false);}
    }
    void load();const timer=setInterval(load,10000);
    return()=>{active=false;clearInterval(timer);};
  },[api,weekOf,retry]);
  return <main className="mx-auto max-w-6xl px-5 py-8">
    <a href="/reports" className="underline">← Daily clinic report</a>
    <div className="my-6 flex flex-wrap justify-between gap-3"><h1 className="text-3xl font-semibold">Weekly visit summary</h1><span className="badge">Staff Demo · synthetic data</span></div>
    <section className="panel mb-5">
      <form className="flex flex-wrap items-end gap-4" onSubmit={e=>{e.preventDefault();setWeekOf(String(new FormData(e.currentTarget).get("week_of")||""));setRetry(n=>n+1);}}>
        <label className="block max-w-xs font-semibold">Week containing<input name="week_of" aria-label="Week containing" type="date" required defaultValue={weekOf} className="mt-2 w-full rounded-lg border p-3"/></label>
        <button type="submit" className="btn">View week</button>
      </form>
      <p className="muted mt-3 text-sm">Choose any date in the week. Weeks run Monday to Sunday in Malaysia time (UTC+8). Current saved appointment statuses refresh every ten seconds.</p>
    </section>
    {error?<div role="alert" className="panel mb-5 text-red-800">{error}<button type="button" className="btn secondary ml-3" onClick={()=>setRetry(n=>n+1)}>Retry weekly report</button></div>:null}
    {loading?<p role="status">Loading weekly visit summary…</p>:null}
    {report?<>
      <section className="panel">
        <h2 className="text-xl font-semibold">{dayLabel(report.week_start)} – {dayLabel(report.week_end)}</h2>
        <p className="muted my-3 text-sm">Counts use the scheduled appointment date, regardless of when a booking was created. Rescheduled original visits are separate from cancellations. All seven days are included, even with zero records.</p>
        <p className="mb-4 font-semibold">{report.visits.total} booking records this week</p>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <caption className="sr-only">Daily appointment status counts and weekly totals</caption>
          <thead><tr><th scope="col">Appointment date</th>{columns.map(([key,label])=><th key={key} scope="col">{label}</th>)}</tr></thead>
          <tbody>{report.days.map(day=><tr key={day.clinic_date}><th scope="row">{dayLabel(day.clinic_date)}</th>{columns.map(([key])=><td key={key}>{day.visits[key]}</td>)}</tr>)}</tbody>
          <tfoot><tr className="font-semibold"><th scope="row">Weekly total</th>{columns.map(([key])=><td key={key}>{report.visits[key]}</td>)}</tr></tfoot>
        </table></div>
        {report.visits.total===0?<p className="muted mt-4">No appointment records for this week.</p>:null}
      </section>
      <p className="muted mt-5 text-sm">Updated {new Date(report.generated_at).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:true})} (Malaysia time, UTC+8). Synthetic records only.</p>
    </>:null}
  </main>;
}
