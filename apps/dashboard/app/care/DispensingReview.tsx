import {Care,Medicine,medicineLabel,queueToken,visitTime} from "@smart-skin/shared";

export default function DispensingReview({record,catalog,busy,onConfirm,onCancel}:{record:Care;catalog:Medicine[];busy:boolean;onConfirm:()=>void;onCancel:()=>void}){
  const {visit,prescription}=record;
  if(!prescription)return null;
  const insufficient=prescription.items.some(item=>{const medicine=catalog.find(m=>m.id===item.medicine_id);return !medicine||medicine.stock<item.quantity;});
  return <section aria-label="Dispensing review" className="mt-4 rounded-xl border border-[#ccdcd4] bg-[#f4f7f6] p-4">
    <h4 className="font-semibold">Review dispensing</h4>
    <p className="my-3">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)}</p>
    <ul className="my-3 space-y-4">{prescription.items.map(item=>{const medicine=catalog.find(m=>m.id===item.medicine_id);const short=!medicine||medicine.stock<item.quantity;return <li key={item.medicine_id}>
      <strong>{medicineLabel(item)} × {item.quantity}</strong>
      <p className="my-2 whitespace-pre-wrap break-words text-sm">{item.directions}</p>
      <p className={`text-sm ${short?"font-semibold text-red-800":"muted"}`}>Required: {item.quantity} units · Current displayed stock: {medicine?`${medicine.stock} units`:"Unavailable"}{short?" · Insufficient stock":""}</p>
      {medicine&&!medicine.active?<p className="muted mt-2 text-sm">Inactive catalogue item · this issued prescription is retained.</p>:null}
    </li>;})}</ul>
    <p className="muted my-3 text-sm">Stock refreshes every three seconds. Confirmation checks the latest stock on the server and deducts all prescribed items together once.</p>
    {insufficient?<p role="alert" className="my-3 text-red-800">Insufficient or unavailable stock. Replenish stock before confirming dispensing.</p>:null}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||insufficient} onClick={onConfirm}>{busy?"Saving…":"Confirm dispensing"}</button><button className="btn secondary" disabled={busy} onClick={onCancel}>Cancel dispensing</button></div>
  </section>;
}
