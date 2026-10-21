import type {InventorySummary} from "@smart-skin/shared";

export const movementColumns=[["received","Received","#176f5e"],["dispensed","Dispensed","#2563eb"],["damaged","Damaged","#b45309"],["lost","Lost","#b91c1c"]] as const;
export const activityLabel=(day:string,granularity:InventorySummary["granularity"])=>new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB",{...(granularity==="day"?{day:"numeric" as const}:{}),month:"short",year:"numeric",timeZone:"UTC"});

export default function InventoryTrend({report}:{report:InventorySummary}){
  const max=Math.max(1,...report.buckets.flatMap(row=>movementColumns.map(([key])=>row.units[key])));
  const step=800/report.buckets.length,width=Math.min(24,step*.18);
  const any=movementColumns.some(([key])=>report.units[key]>0);
  return <section className="panel mb-5 min-w-0"><h2 className="text-xl font-semibold">Stock movements by {report.granularity}</h2>
    <p className="muted my-3 text-sm">Activity dates in Malaysia time. Outgoing quantities are shown as positive units; net movement is shown separately below.</p>
    <ul aria-label="Movement chart legend" className="mb-4 flex flex-wrap gap-5">{movementColumns.map(([key,label,color])=><li key={key} className="flex items-center gap-2"><span aria-hidden="true" className="inline-block h-3 w-3 rounded" style={{backgroundColor:color}}/>{label}</li>)}</ul>
    {any?<div className="overflow-x-auto"><svg role="img" aria-labelledby="inventory-trend-title inventory-trend-description" viewBox="0 0 900 260" className="w-full" style={{minWidth:report.granularity==="day"?960:460}}>
      <title id="inventory-trend-title">Inventory activity by {report.granularity}</title><desc id="inventory-trend-description">Grouped bars compare received, dispensed, damaged and lost quantities. Exact counts are in the activity table.</desc>
      <line x1="52" x2="860" y1="205" y2="205" stroke="#637970"/><line x1="52" x2="860" y1="35" y2="35" stroke="#dce6e0"/>
      <text x="43" y="210" textAnchor="end" fontSize="14" fill="#637970">0</text><text x="43" y="40" textAnchor="end" fontSize="14" fill="#637970">{max}</text>
      {report.buckets.map((row,index)=>{
        const center=58+(index+.5)*step;
        const short=report.granularity==="day"?String(Number(row.start_date.slice(8))):new Date(`${row.start_date}T00:00:00Z`).toLocaleDateString("en-GB",{month:"short",timeZone:"UTC"});
        return <g key={row.start_date}>{movementColumns.map(([key,label,color],series)=>{
          const height=row.units[key]/max*170;
          return <rect key={key} x={center+(series-2)*width} y={205-height} width={width*.85} height={height} rx="2" fill={color}><title>{activityLabel(row.start_date,report.granularity)} · {label}: {row.units[key]} units</title></rect>;
        })}<text x={center} y="230" textAnchor="middle" fontSize="14" fill="#637970">{short}</text></g>;
      })}
    </svg></div>:<p className="py-12 text-center">No recorded stock movements in this period.</p>}
  </section>;
}
