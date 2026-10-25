import {Care,Invoice,money,queueToken,visitTime} from "@smart-skin/shared";

export default function BillReview({record,lines,changed,busy,onConfirm,onCancel}:{record:Care;lines:Invoice["lines"];changed:boolean;busy:boolean;onConfirm:()=>void;onCancel:()=>void}){
  const total=lines.reduce((sum,line)=>sum+line.quantity*line.unit_price_cents,0);
  return <section aria-label="Bill review" className="mt-4 rounded-xl border border-[#ccdcd4] bg-[#f4f7f6] p-4">
    <h4 className="font-semibold">Review bill · simulation</h4>
    <p className="my-3">{queueToken(record.visit)} · {record.visit.patient_name} · {record.visit.doctor_name} · {visitTime(record.visit.starts_at)}</p>
    <ul className="my-3 space-y-4">{lines.map((line,index)=><li key={index}><strong>{line.description} × {line.quantity}</strong><p className="mt-1 text-sm">{money(line.unit_price_cents)} per unit · Line total {money(line.unit_price_cents*line.quantity)}</p></li>)}</ul>
    <p className="my-4 border-t border-[#ccdcd4] pt-3 font-semibold">Total {money(total)} · simulation</p>
    {(!record.prescription||record.prescription.status==="cancelled")?<p className="my-3 text-sm">Consultation only. No active prescription is included; cancelled medicines are excluded.</p>:null}
    <p className="muted my-3 text-sm">Prescription items use their saved prices. Confirmation creates a fixed unpaid bill. No payment is recorded and no stock is deducted.</p>
    {changed?<p role="alert" className="my-3 text-red-800">The visit changed. Cancel and review the bill again.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||changed} onClick={onConfirm}>{busy?"Saving…":"Confirm bill"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Cancel bill review</button></div>
  </section>;
}
