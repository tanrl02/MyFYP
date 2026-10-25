import {Care,money,queueToken,visitTime} from "@smart-skin/shared";

export default function PaymentReview({record,busy,onConfirm,onCancel}:{record:Care;busy:boolean;onConfirm:()=>void;onCancel:()=>void}){
  const {visit,invoice,prescription}=record;
  if(!invoice)return null;
  const needsDispensing=prescription?.status==="issued";
  return <section aria-label="Simulated payment review" className="mt-4 rounded-xl border border-[#ccdcd4] bg-[#f4f7f6] p-4">
    <h4 className="font-semibold">Review simulated payment</h4>
    <p className="my-3">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)}</p>
    <p className="muted my-3 text-sm">Bill {invoice.id.slice(0,8)} · Unpaid</p>
    <ul className="my-3 space-y-3">{invoice.lines.map((line,index)=><li key={index} className="flex flex-wrap justify-between gap-2 text-sm"><span>{line.description} × {line.quantity}</span><strong>{money(line.unit_price_cents*line.quantity)}</strong></li>)}</ul>
    <p className="my-4 border-t border-[#ccdcd4] pt-3 font-semibold">Total to record: {money(invoice.total_cents)} · simulation</p>
    <p className="muted my-3 text-sm">Confirmation marks this bill Paid · simulation. No money is transferred. The saved bill items and total stay unchanged.</p>
    {needsDispensing?<p role="alert" className="my-3 text-red-800">Dispense the prescription before recording simulated payment.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||needsDispensing||invoice.status!=="unpaid"} onClick={onConfirm}>{busy?"Saving…":"Confirm simulated payment"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Cancel payment review</button></div>
  </section>;
}
