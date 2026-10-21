import type {VisitSummary} from "@smart-skin/shared";

export const statusColumns=[["waiting","Waiting"],["called","Called"],["completed","Completed"],["cancelled","Cancelled"],["missed","Missed"],["rescheduled","Rescheduled"]] as const;
export const bucketLabel=(day:string,granularity:VisitSummary["granularity"])=>new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB",{...(granularity==="day"?{day:"numeric" as const}:{}),month:"short",year:"numeric",timeZone:"UTC"});

export function VisitTrendChart({report}:{report:VisitSummary}){
  const maximum=Math.max(1,...report.buckets.map(row=>row.visits.total));
  const step=800/report.buckets.length;
  return <section className="panel min-w-0">
    <h2 className="text-xl font-semibold">Scheduled records by {report.granularity}</h2>
    <p className="muted my-3 text-sm">Each bar counts saved appointment records. Exact values and status counts are in the table below.</p>
    {report.visits.total===0?<p className="py-12 text-center">No scheduled records in this period.</p>:<div className="overflow-x-auto">
      <svg role="img" aria-labelledby="visit-trend-title visit-trend-description" viewBox="0 0 900 260" className="w-full" style={{minWidth:report.granularity==="day"?720:420}}>
        <title id="visit-trend-title">Scheduled booking records by {report.granularity}</title>
        <desc id="visit-trend-description">Bar heights compare booking record counts. Use the detailed table for all values.</desc>
        <line x1="52" x2="860" y1="205" y2="205" stroke="#637970"/>
        <line x1="52" x2="860" y1="35" y2="35" stroke="#dce6e0"/>
        <text x="43" y="209" textAnchor="end" fontSize="16" fill="#637970">0</text>
        <text x="43" y="39" textAnchor="end" fontSize="16" fill="#637970">{maximum}</text>
        {report.buckets.map((row,index)=>{
          const height=row.visits.total/maximum*170,width=Math.min(42,step*.7),x=58+index*step+(step-width)/2;
          const short=report.granularity==="day"?String(Number(row.start_date.slice(8))):new Date(`${row.start_date}T00:00:00Z`).toLocaleDateString("en-GB",{month:"short",timeZone:"UTC"});
          return <g key={row.start_date}><title>{bucketLabel(row.start_date,report.granularity)}: {row.visits.total} records</title><rect x={x} y={205-height} width={width} height={height} rx="3" fill="#176f5e"/>{row.visits.total>0?<text x={x+width/2} y={198-height} textAnchor="middle" fontSize="16" fill="#19352e">{row.visits.total}</text>:null}<text x={x+width/2} y="227" textAnchor="middle" fontSize="16" fill="#637970">{short}</text></g>;
        })}
      </svg>
    </div>}
  </section>;
}

export function VisitStatusChart({report}:{report:VisitSummary}){
  return <section className="panel min-w-0"><h2 className="text-xl font-semibold">Current booking statuses</h2>
    <p className="muted my-3 text-sm">Shares of all {report.visits.total} booking records, including rescheduled originals. These are not treatment outcomes.</p>
    <ul aria-label="Booking status breakdown" className="space-y-3">{statusColumns.map(([key,label])=>{
      const value=report.visits[key],percent=report.visits.total?value/report.visits.total*100:0;
      return <li key={key}><div className="mb-1 flex justify-between gap-3"><span>{label}</span><strong>{value} · {percent.toFixed(1)}%</strong></div><div aria-hidden="true" className="h-3 overflow-hidden rounded bg-[#e7efeb]"><div className="h-full rounded bg-[#176f5e]" style={{width:`${percent}%`}}/></div></li>;
    })}</ul>
  </section>;
}

export function VisitAnalysis({report}:{report:VisitSummary}){
  const current=report.visits.total,previous=report.previous.visits.total,difference=current-previous;
  const peak=Math.max(0,...report.buckets.map(row=>row.visits.total));
  const busiest=peak?report.buckets.filter(row=>row.visits.total===peak):[];
  return <section className="panel mb-5"><h2 className="text-xl font-semibold">Period analysis</h2>
    <div className="mt-4 grid gap-5 md:grid-cols-2"><div><h3 className="font-semibold">Compared with the previous {report.period}</h3>
      <p className="mt-2">{bucketLabel(report.previous.start_date,"day")} – {bucketLabel(report.previous.end_date,"day")}: {previous} {previous===1?"record":"records"}.</p>
      <p className="mt-2">{difference===0?"No change in record count.":`${Math.abs(difference)} ${difference>0?"more":"fewer"} ${Math.abs(difference)===1?"record":"records"}.`}{previous>0?` ${Math.abs(difference/previous*100).toFixed(1)}% ${difference>0?"higher":difference<0?"lower":"change"}.`:" Percentage change is unavailable because the previous count is zero."}</p>
    </div><div><h3 className="font-semibold">Highest scheduled volume</h3><p className="mt-2">{busiest.length?`${busiest.slice(0,3).map(row=>bucketLabel(row.start_date,report.granularity)).join(", ")}${busiest.length>3?` and ${busiest.length-3} other ${report.granularity}s`:""}: ${peak} ${peak===1?"record":"records"}${busiest.length>1?" each":""}.`:"No busiest day or month: this period has no records."}</p></div></div>
    <p className="muted mt-4 text-sm">Comparison uses full calendar periods and current saved statuses, including future scheduled appointments. It is not a forecast or a comparison of equal elapsed time. Zero-count days and months are included.</p>
  </section>;
}
