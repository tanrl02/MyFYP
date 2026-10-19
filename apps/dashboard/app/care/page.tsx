"use client";
import { useEffect, useMemo, useState } from "react";
import { Care, Invoice, DemoActor, DemoApi, Medicine, PrescriptionItem, medicineLabel, money, queueToken, visitTime } from "@smart-skin/shared";

import SimulatedReceipt from "./SimulatedReceipt";
import PaymentReview from "./PaymentReview";
import BillReview from "./BillReview";
import DispensingReview from "./DispensingReview";

const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function CarePage() {
  const [actor, setActor] = useState<DemoActor>("doctor-lim");
  const api = useMemo(() => new DemoApi(base, actor), [actor]);
  const [records, setRecords] = useState<Care[]>([]);
  const [catalog, setCatalog] = useState<Medicine[]>([]);
  const [careFilter,setCareFilter]=useState<"all"|"dispensing"|"unpaid">("all");
  const [selected, setSelected] = useState("");
  const [receipt,setReceipt]=useState<Care|null>(null);
  const [paymentReview,setPaymentReview]=useState("");
  const [billReview,setBillReview]=useState<{visitId:string;prescriptionId:string|null;lines:Invoice["lines"]}|null>(null);
  const reviewedVisit=records.find(record=>record.visit.id===billReview?.visitId);
  const billReviewChanged=!!billReview&&(!reviewedVisit||reviewedVisit.visit.status!=="completed"||(reviewedVisit.prescription?.id??null)!==billReview.prescriptionId);
  const [dispensing,setDispensing]=useState("");
  const [medicineSearch,setMedicineSearch]=useState("");
  const searchTerm=medicineSearch.trim().toLowerCase();
  const visibleCatalog=catalog.filter(m=>!searchTerm||[m.name,m.strength,m.form].some(value=>value.toLowerCase().includes(searchTerm)));
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const chosenItems=Object.entries(quantities).filter(([,quantity])=>Number(quantity)>0);
  const [directions, setDirections] = useState("Demo instructions only — not medical advice.");
  const [review,setReview]=useState<{visitId:string;items:(PrescriptionItem & Pick<Medicine,"name"|"strength"|"form"|"version">)[]}|null>(null);
  const reviewChanged=!!review&&review.items.some(item=>{const current=catalog.find(m=>m.id===item.medicine_id);return !current||current.version!==item.version||medicineLabel(current)!==medicineLabel(item);});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const staff = actor === "staff-demo";
  useEffect(() => {
    let active = true, fetching = false;
    setRecords([]); setCatalog([]); setCareFilter("all"); setReceipt(null); setDispensing(""); setPaymentReview(""); setBillReview(null); setSelected(""); setReview(null); setQuantities({}); setMedicineSearch(""); setNotice(""); setError(""); setLoading(true);
    async function load() {
      if (fetching) return; fetching = true;
      try {
        const [care, medicines] = await Promise.all([api.care(), api.medicines()]);
        if (active) { setRecords(care); setCatalog(medicines); setError(""); }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Cannot load visits."); }
      finally { fetching = false; if (active) setLoading(false); }
    }
    void load(); const timer = setInterval(load, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [api]);
  async function action(fn: () => Promise<unknown>, message: string) {
    if (busy) return; setBusy(true); setNotice(""); setError("");
    try {
      await fn(); setDispensing(""); setPaymentReview(""); setBillReview(null); setSelected(""); setReview(null);
      const [care, medicines] = await Promise.all([api.care(), api.medicines()]);
      setRecords(care); setCatalog(medicines); setNotice(message);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save. Refresh before retrying."); }
    finally { setBusy(false); }
  }
  function reviewPrescription(visitId: string) {
    if (Object.values(quantities).some(q => !Number.isInteger(Number(q)) || Number(q) < 0 || Number(q) > 20)) { setError("Quantities must be whole numbers from 0 to 20. Zero leaves an item out."); return; }
    if(Object.entries(quantities).some(([id,value])=>Number(value)>0&&!catalog.some(item=>item.id===id))){setError("A selected medicine is no longer active. Cancel and reopen the prescription to review current choices.");return;}
    const items: PrescriptionItem[] = catalog.filter(m => Number(quantities[m.id]) > 0).map(m => ({ medicine_id: m.id, quantity: Number(quantities[m.id]), directions: directions.trim() }));
    if (!items.length || !directions.trim() || items.some(i => !Number.isInteger(i.quantity) || i.quantity > 20)) { setError("Select at least one item with a whole quantity from 1 to 20 and enter demo directions."); return; }
    setError("");
    setReview({visitId,items:items.map(item=>{const medicine=catalog.find(m=>m.id===item.medicine_id)!;return {...item,name:medicine.name,strength:medicine.strength,form:medicine.form,version:medicine.version};})});
  }
  function confirmPrescription(visitId:string){
    if(!review||review.visitId!==visitId||busy)return;
    if(reviewChanged){setError("Medicine details changed. Keep editing and review the current choices again.");return;}
    const items=review.items.map(({medicine_id,quantity,directions})=>({medicine_id,quantity,directions}));
    void action(()=>api.prescribe(visitId,items),"Prescription issued. Staff and patient can see the saved items.");
  }
  function confirmDispensing(record:Care){
    const prescription=record.prescription;
    if(!staff||busy||!prescription||prescription.status!=="issued"||dispensing!==prescription.id)return;
    if(prescription.items.some(item=>{const medicine=catalog.find(m=>m.id===item.medicine_id);return !medicine||medicine.stock<item.quantity;})){
      setError("Insufficient or unavailable stock. Nothing was dispensed. Review the latest stock.");return;
    }
    void action(()=>api.dispense(prescription.id),"Dispensing saved. Stock deducted once.");
  }
  function reviewBill(record:Care){
    if(!staff||busy||record.visit.status!=="completed"||record.invoice)return;
    setError("");
    setBillReview({visitId:record.visit.id,prescriptionId:record.prescription?.id??null,lines:[{description:"Demo consultation",quantity:1,unit_price_cents:3000},...(record.prescription?.items??[]).map(item=>({description:medicineLabel(item),quantity:item.quantity,unit_price_cents:item.price_cents}))]});
  }
  function confirmBill(record:Care){
    if(!staff||busy||!billReview||billReview.visitId!==record.visit.id||record.invoice)return;
    if(billReviewChanged){setError("The visit changed. Cancel and review the bill again.");return;}
    void action(()=>api.invoice(record.visit.id,{prescription_id:billReview.prescriptionId}),"Itemised demo bill saved. Patient can now view it.");
  }
  function confirmPayment(record:Care){
    const invoice=record.invoice;
    if(!staff||busy||!invoice||invoice.id!==paymentReview||invoice.status!=="unpaid")return;
    if(record.prescription&&record.prescription.status!=="dispensed"){
      setError("Dispense the prescription before recording simulated payment.");return;
    }
    void action(()=>api.paySimulated(invoice.id),"Simulated payment saved. No money was transferred.");
  }
  const consultationVisits=records.filter(r=>r.visit.status==="called"||r.visit.status==="completed");
  const visits=consultationVisits.filter(record=>!staff||careFilter==="all"||(careFilter==="dispensing"?record.prescription?.status==="issued":record.invoice?.status==="unpaid"));
  if(staff&&receipt?.invoice?.status==="paid")return <SimulatedReceipt record={receipt} onClose={()=>setReceipt(null)}/>;
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Visit care & billing</p></div><nav className="flex flex-wrap gap-3">{staff?<a className="btn secondary" href="/stock">Stock</a>:null}<a className="btn secondary" href="/consultations">Consultation notes</a><a className="btn secondary" href="/reviews">Doctor reviews</a><a className="btn secondary" href="/">← Patient queue</a></nav></header>
    <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Synthetic demonstration. Demo identities are not secure login. Items are placeholders, not medication. All prices and payments are simulated; no money moves.</div>
    <h1 className="mb-2 text-3xl font-semibold">From consultation to checkout.</h1><p className="muted mb-6">Doctor issues → staff dispenses → completed visit is billed → simulated payment.</p>
    <section className="panel mb-6"><label className="text-sm font-semibold">Demo role<select className="mt-2" disabled={busy} value={actor} onChange={e => setActor(e.target.value as DemoActor)}><option value="doctor-lim">Dr. Lim (demo)</option><option value="doctor-anita">Dr. Anita (demo)</option><option value="staff-demo">Staff Demo — dispensing & billing</option></select></label><p className="muted mt-3 text-sm">{staff ? "Staff view operational prescription and bill details." : "Doctors see only their assigned visits. Call a patient from the queue before issuing."}</p></section>
    {staff&&!loading?<section aria-label="Staff care filters" className="panel mb-6"><label className="text-sm font-semibold">Care list<select disabled={busy} value={careFilter} onChange={e=>{setCareFilter(e.target.value as "all"|"dispensing"|"unpaid");setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}><option value="all">All</option><option value="dispensing">Awaiting dispensing</option><option value="unpaid">Unpaid bills</option></select></label><p role="status" className="muted mt-3 text-sm">Showing {visits.length} of {consultationVisits.length} consultation visits{careFilter==="dispensing"?" awaiting dispensing":careFilter==="unpaid"?" with unpaid bills":""}. Refreshes every three seconds.</p></section>:null}
    {error && <div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div>}
    {notice && <div role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</div>}
    {loading && <p className="muted">Loading saved visits…</p>}
    {!loading&&visits.length===0&&<div className="panel"><h2 className="font-semibold">{staff&&consultationVisits.length>0?(careFilter==="dispensing"?"No prescriptions awaiting dispensing.":"No unpaid bills."):"No consultation visits yet"}</h2><p className="muted mt-2">{staff&&consultationVisits.length>0?"Choose All to view the other consultation visits.":"Book and call a patient from the queue, then choose the assigned doctor here."}</p></div>}
    <div className="grid gap-6">{visits.map(({ visit, prescription, invoice }) => <section key={visit.id} className="panel">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">{queueToken(visit)} · {visit.patient_name}</h2><p className="muted mt-1 text-sm">{visit.doctor_name} · {visitTime(visit.starts_at)}</p></div><span className="badge">{visit.status}</span></div>
      <div className="grid gap-6 md:grid-cols-2"><div><h3 className="mb-3 font-semibold">Prescription</h3>
        {prescription ? <><span className="badge">{prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing"}</span><ul className="my-4 space-y-3">{prescription.items.map(item => <li key={item.medicine_id}><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="muted text-sm">{item.directions}</p></li>)}</ul>{staff && prescription.status === "issued" && (dispensing===prescription.id?<DispensingReview record={{visit,prescription,invoice}} catalog={catalog} busy={busy} onConfirm={()=>confirmDispensing({visit,prescription,invoice})} onCancel={()=>{setDispensing("");setError("");}}/>:<button className="btn" disabled={busy} onClick={()=>{setDispensing(prescription.id);setError("");}}>Review dispensing</button>)}</> : <>
          <p className="muted mb-3 text-sm">No prescription issued.{invoice ? " This visit has been billed; new items cannot be added." : " Issue before generating a bill if items are needed."}</p>
          {!staff && !invoice && selected !== visit.id && <button className="btn" disabled={busy} onClick={() => { setSelected(visit.id); setReview(null); setQuantities({}); setMedicineSearch(""); setDirections("Demo instructions only — not medical advice."); setError(""); }}>Create prescription</button>}
          {!staff && selected === visit.id && <div className="rounded-xl bg-[#f4f7f6] p-4"><fieldset disabled={busy||!!review}><p className="muted mb-3 text-sm">Issued items are fixed for this demo. Check quantities before saving.</p><label className="mb-3 block text-sm">Search prescription medicines<input type="search" disabled={busy} maxLength={100} value={medicineSearch} onChange={e=>setMedicineSearch(e.target.value)} placeholder="Name, strength or form" className="mt-2 w-full rounded-lg border border-[#ccdcd4] bg-white p-2"/></label><button className="btn secondary mb-3" disabled={busy||!medicineSearch} onClick={()=>setMedicineSearch("")}>Clear medicine search</button><p role="status" className="muted mb-3 text-sm">Showing {visibleCatalog.length} of {catalog.length} active medicines. Search keeps selected quantities.</p>{chosenItems.length?<div className="mb-3 rounded-lg border border-[#ccdcd4] bg-white p-3"><h4 className="font-semibold">Selected medicines ({chosenItems.length})</h4><ul className="mt-2 space-y-2">{chosenItems.map(([id,quantity])=>{const medicine=catalog.find(m=>m.id===id);return <li key={id}>{medicine?medicineLabel(medicine):"Unavailable medicine — cancel and reopen to review"} × {quantity}</li>;})}</ul></div>:<p className="muted mb-3 text-sm">No medicines selected yet.</p>}{visibleCatalog.length===0?<p className="mb-3 text-sm">{searchTerm?"No active medicines match your search. Clear search to view all choices.":"No active medicines available."}</p>:null}{visibleCatalog.map(m => <label key={m.id} className="mb-3 block text-sm">{medicineLabel(m)} · {money(m.price_cents)} · {m.stock} in stock<input aria-label={`Quantity ${m.id}`} className="mt-2 block w-full rounded-lg border border-[#ccdcd4] bg-white p-2" type="number" min="0" max="20" step="1" disabled={busy} value={quantities[m.id] || "0"} onChange={e => setQuantities(q => ({ ...q, [m.id]: e.target.value }))} /></label>)}<label className="block text-sm">Demo directions<textarea className="mt-2 w-full rounded-lg border border-[#ccdcd4] p-2" maxLength={300} disabled={busy} value={directions} onChange={e => setDirections(e.target.value)} /></label></fieldset>{review&&review.visitId===visit.id?<section aria-label="Prescription review" className="mt-4 rounded-lg border border-[#ccdcd4] bg-white p-4"><h4 className="font-semibold">Review prescription</h4><p className="my-3">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)}</p><ul className="my-3 space-y-3">{review.items.map(item=><li key={item.medicine_id}><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="whitespace-pre-wrap break-words text-sm">{item.directions}</p></li>)}</ul><p className="muted my-3 text-sm">Confirming saves these quantities and directions as a fixed prescription. Staff will check stock when dispensing.</p>{reviewChanged?<p role="alert" className="my-3 text-red-800">Medicine details changed. Keep editing and review the current choices again.</p>:null}<div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||reviewChanged} onClick={()=>confirmPrescription(visit.id)}>{busy?"Saving…":"Confirm issue prescription"}</button><button className="btn secondary" disabled={busy} onClick={()=>{setReview(null);setError("");}}>Keep editing prescription</button><button className="btn secondary" disabled={busy} onClick={()=>{setReview(null);setSelected("");setError("");}}>Cancel prescription</button></div></section>:<div className="mt-4 flex flex-wrap gap-3"><button className="btn" disabled={busy} onClick={() => reviewPrescription(visit.id)}>Review prescription</button><button className="btn secondary" disabled={busy} onClick={() => setSelected("")}>Cancel</button></div>}</div>}
        </>}
      </div><div><h3 className="mb-3 font-semibold">Bill · simulation</h3>{invoice ? <><ul className="space-y-3">{invoice.lines.map((line, i) => <li key={i} className="flex justify-between gap-3 text-sm"><span>{line.description} × {line.quantity}</span><strong>{money(line.unit_price_cents * line.quantity)}</strong></li>)}</ul><div className="my-4 flex items-center justify-between border-t border-[#dce6e0] pt-4"><strong>Total {money(invoice.total_cents)}</strong><span className="badge">{invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}</span></div>{staff && invoice.status === "unpaid" && (paymentReview===invoice.id?<PaymentReview record={{visit,prescription,invoice}} busy={busy} onConfirm={()=>confirmPayment({visit,prescription,invoice})} onCancel={()=>{setPaymentReview("");setError("");}}/>:<button className="btn" disabled={busy || (!!prescription && prescription.status !== "dispensed")} onClick={()=>{setPaymentReview(invoice.id);setError("");}}>Review simulated payment</button>)}{invoice.status === "paid" && <><p className="muted text-sm">Demo receipt {invoice.id.slice(0, 8)} · {invoice.paid_at ? visitTime(invoice.paid_at) : ""}</p>{staff?<button className="btn secondary mt-3" disabled={busy} onClick={()=>setReceipt({visit,prescription,invoice})}>View simulated receipt</button>:null}</>}{prescription?.status === "issued" && <p className="muted mt-3 text-sm">Dispense before recording payment.</p>}</> : <><p className="muted mb-3 text-sm">Complete the visit, then generate a fixed itemised bill. Demo consultation: RM 30.00.</p>{staff && (billReview?.visitId===visit.id?<BillReview record={{visit,prescription,invoice}} lines={billReview.lines} changed={billReviewChanged} busy={busy} onConfirm={()=>confirmBill({visit,prescription,invoice})} onCancel={()=>{setBillReview(null);setError("");}}/>:<button className="btn" disabled={busy || visit.status !== "completed"} onClick={()=>reviewBill({visit,prescription,invoice})}>Review bill</button>)}</>}</div></div>
    </section>)}</div>
  </main>;
}
