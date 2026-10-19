import {Care,money,queueToken} from "@smart-skin/shared";

export default function SimulatedReceipt({record,onClose}:{record:Care;onClose:()=>void}){
  const {visit,invoice}=record;
  if(!invoice||invoice.status!=="paid")return null;
  const dateTime=(value:string)=>new Date(value).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
  return <main className="simulated-receipt mx-auto max-w-4xl px-5 py-8">
    <div className="receipt-actions mb-6"><div className="flex flex-wrap gap-3"><button className="btn secondary" onClick={onClose}>Back to care & bills</button><button className="btn" onClick={()=>window.print()}>Print / Save as PDF</button></div><p className="muted mt-3 text-sm">Use your browser’s print dialog to print or choose Save as PDF.</p></div>
    <article className="receipt-sheet panel">
      <header><p className="text-lg font-semibold">Smart Skin</p><h1 className="my-3 text-3xl font-semibold">Simulated receipt</h1><p className="receipt-simulation my-4 border-2 border-[#176f5e] p-3 font-semibold">Simulation — no money transferred</p></header>
      <dl className="my-6 grid gap-4 sm:grid-cols-2"><div><dt className="muted text-sm">Patient</dt><dd className="font-semibold">{visit.patient_name}</dd></div><div><dt className="muted text-sm">Visit</dt><dd>{queueToken(visit)} · {visit.doctor_name}</dd></div><div><dt className="muted text-sm">Visit date · Malaysia time</dt><dd>{dateTime(visit.starts_at)}</dd></div><div><dt className="muted text-sm">Payment recorded · Malaysia time</dt><dd>{invoice.paid_at?dateTime(invoice.paid_at):"Not recorded"}</dd></div><div className="sm:col-span-2"><dt className="muted text-sm">Receipt / bill ID</dt><dd className="break-all text-sm">{invoice.id}</dd></div></dl>
      <table className="w-full text-sm"><caption className="mb-3 text-left font-semibold">Saved itemised charges</caption><thead><tr><th scope="col">Description</th><th scope="col">Qty</th><th scope="col">Unit price</th><th scope="col">Amount</th></tr></thead><tbody>{invoice.lines.map((line,index)=><tr key={index}><td className="break-words">{line.description}</td><td>{line.quantity}</td><td className="whitespace-nowrap">{money(line.unit_price_cents)}</td><td className="whitespace-nowrap">{money(line.unit_price_cents*line.quantity)}</td></tr>)}</tbody><tfoot><tr><th scope="row" colSpan={3}>Total · simulation</th><td className="whitespace-nowrap font-semibold">{money(invoice.total_cents)}</td></tr></tfoot></table>
      <p className="my-5 font-semibold">Paid · simulation</p><footer className="muted border-t border-[#dce6e0] pt-4 text-sm">Fictional demonstration data. This receipt records a simulated payment only. Amounts and item descriptions come from the saved bill.</footer>
    </article>
  </main>;
}
