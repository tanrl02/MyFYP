"use client";
import { useEffect, useMemo, useState } from "react";
import { Care, Invoice, DispensingAllocation, DemoActor, DemoApi, Medicine, PrescriptionItem, medicineLabel, money, queueToken, visitTime } from "@smart-skin/shared";

import SimulatedReceipt from "./SimulatedReceipt";
import PaymentReview from "./PaymentReview";
import BillReview from "./BillReview";
import DispensingReview from "./DispensingReview";
import DispensingHistory from "./DispensingHistory";
import { CheckoutTarget, readCheckoutTarget } from "../checkoutNavigation";
import PrescribingBackground from "./PrescribingBackground";
import CheckoutChecklist from "./CheckoutChecklist";

const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function CarePage() {
  const [checkoutTarget,setCheckoutTarget]=useState<CheckoutTarget|null>(null);
  useEffect(()=>{if(readCheckoutTarget(window.location.search))setActor("staff-demo");},[]);
  const [actor, setActor] = useState<DemoActor>("doctor-lim");
  const api = useMemo(() => new DemoApi(base, actor), [actor]);
  const [records, setRecords] = useState<Care[]>([]);
  const [catalog, setCatalog] = useState<Medicine[]>([]);
  const [careDoctor,setCareDoctor]=useState<"all"|"doctor-lim"|"doctor-anita">("all");
  const [careDate,setCareDate]=useState("");
  const [careSort,setCareSort]=useState<"newest"|"oldest">("newest");
  const [careSearch,setCareSearch]=useState("");
  const careSearchTerm=careSearch.trim().toLowerCase();
  const [careFilter,setCareFilter]=useState<"all"|"checkout"|"dispensing"|"billing"|"unpaid">("all");
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
    const target=actor==="staff-demo"?readCheckoutTarget(window.location.search):null;
    setCheckoutTarget(target);
    setRecords([]); setCatalog([]); setCareSort("newest"); setCareFilter("all"); setCareDoctor((target?.doctor as "doctor-lim"|"doctor-anita")||"all"); setCareDate(target?.date||""); setCareSearch(""); setReceipt(null); setDispensing(""); setPaymentReview(""); setBillReview(null); setSelected(""); setReview(null); setQuantities({}); setMedicineSearch(""); setNotice(""); setError(""); setLoading(true);
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
  async function confirmDispensing(record:Care,allocations:DispensingAllocation[]){
    const prescription=record.prescription;
    if(!staff||busy||!prescription||prescription.status!=="issued"||dispensing!==prescription.id)return;
    if(prescription.items.some(item=>{const medicine=catalog.find(m=>m.id===item.medicine_id);return !medicine||medicine.stock<item.quantity;})){
      throw new Error("Insufficient or unavailable stock. Nothing was dispensed. Review the latest stock.");
    }
    setBusy(true);setError("");setNotice("");
    try{
      await api.dispense(prescription.id,allocations);setDispensing("");setNotice("Dispensing saved. Stock and allocations deducted once.");
      try{const [care,medicines]=await Promise.all([api.care(),api.medicines()]);setRecords(care);setCatalog(medicines);}catch{setError("Dispensing saved. Current stock refresh failed; retrying automatically.");}
    }finally{setBusy(false);}
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
  const scopedVisits=consultationVisits.filter(record=>!staff||((careDoctor==="all"||record.visit.doctor_id===careDoctor)&&(!careDate||record.visit.clinic_date===careDate)&&(!careSearchTerm||[record.visit.patient_name,queueToken(record.visit)].some(value=>value.toLowerCase().includes(careSearchTerm)))));
  function matchesWork(record:Care,filter:typeof careFilter){
    return filter==="all"||(filter==="checkout"?record.visit.status==="called"&&!!record.visit.consultation_finished_at:filter==="dispensing"?record.prescription?.status==="issued":filter==="billing"?record.visit.status==="completed"&&!record.invoice:record.invoice?.status==="unpaid");
  }
  const workload: {filter:typeof careFilter;label:string}[]=[{filter:"checkout",label:"Ready for checkout"},{filter:"dispensing",label:"Awaiting dispensing"},{filter:"billing",label:"Awaiting bill"},{filter:"unpaid",label:"Unpaid bills"}];
  const visits=scopedVisits.filter(record=>!staff||matchesWork(record,careFilter));
  if(staff)visits.sort((a,b)=>{
    const timeDifference=Date.parse(a.visit.starts_at)-Date.parse(b.visit.starts_at);
    return (careSort==="oldest"?timeDifference:-timeDifference)||a.visit.queue_number-b.visit.queue_number||a.visit.id.localeCompare(b.visit.id);
  });
  function selectCareFilter(filter:typeof careFilter){
    setCareFilter(filter);setDispensing("");setBillReview(null);setPaymentReview("");setError("");
  }
  if(staff&&receipt?.invoice?.status==="paid")return <SimulatedReceipt record={receipt} onClose={()=>setReceipt(null)}/>;
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Visit care & billing</p></div><nav className="flex flex-wrap gap-3">{staff?<a className="btn secondary" href="/stock">Stock</a>:null}<a className="btn secondary" href="/consultations">Consultation notes</a><a className="btn secondary" href="/reviews">Doctor reviews</a><a className="btn secondary" href="/">← Patient queue</a></nav></header>
    <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Synthetic demonstration. Demo identities are not secure login. Items are placeholders, not medication. All prices and payments are simulated; no money moves.</div>
    <h1 className="mb-2 text-3xl font-semibold">From consultation to checkout.</h1><p className="muted mb-6">Doctor issues → staff dispenses → completed visit is billed → simulated payment.</p>
    <section className="panel mb-6"><label className="text-sm font-semibold">Demo role<select className="mt-2" disabled={busy} value={actor} onChange={e => setActor(e.target.value as DemoActor)}><option value="doctor-lim">Dr. Lim (demo)</option><option value="doctor-anita">Dr. Anita (demo)</option><option value="staff-demo">Staff Demo — dispensing & billing</option></select></label><p className="muted mt-3 text-sm">{staff ? "Staff view operational prescription and bill details." : "Doctors see only their assigned visits. Call a patient from the queue before issuing."}</p></section>
    {staff&&!loading?<section aria-label="Staff care filters" className="panel mb-6"><label className="block text-sm font-semibold">Search patient or queue number<input type="search" maxLength={100} disabled={busy} value={careSearch} onChange={e=>{setCareSearch(e.target.value);setDispensing("");setBillReview(null);setPaymentReview("");setError("");}} placeholder="Patient name or queue number" className="mt-2 w-full rounded-lg border border-[#ccdcd4] bg-white p-3"/></label><button className="btn secondary my-3" disabled={busy||!careSearch} onClick={()=>{setCareSearch("");setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}>Clear care search</button><label className="block text-sm font-semibold">Care list<select disabled={busy} value={careFilter} onChange={e=>selectCareFilter(e.target.value as typeof careFilter)}><option value="all">All</option><option value="checkout">Ready for checkout</option><option value="dispensing">Awaiting dispensing</option><option value="billing">Awaiting bill</option><option value="unpaid">Unpaid bills</option></select></label><label className="mt-4 block text-sm font-semibold">Visit doctor<select disabled={busy} value={careDoctor} onChange={e=>{setCareDoctor(e.target.value as "all"|"doctor-lim"|"doctor-anita");setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}><option value="all">All doctors</option><option value="doctor-lim">Dr. Lim (demo)</option><option value="doctor-anita">Dr. Anita (demo)</option></select></label><label className="mt-4 block text-sm font-semibold">Visit date · Malaysia time<input type="date" disabled={busy} value={careDate} onChange={e=>{setCareDate(e.target.value);setDispensing("");setBillReview(null);setPaymentReview("");setError("");}} className="mt-2 w-full rounded-lg border border-[#ccdcd4] bg-white p-3"/></label><button className="btn secondary mt-3" disabled={busy||!careDate} onClick={()=>{setCareDate("");setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}>All dates</button><button className="btn secondary ml-3 mt-3" disabled={busy||(!careSearch&&careFilter==="all"&&careDoctor==="all"&&!careDate)} onClick={()=>{setCareSearch("");setCareFilter("all");setCareDoctor("all");setCareDate("");setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}>Reset all filters</button><p role="status" className="muted mt-3 text-sm">Showing {visits.length} of {consultationVisits.length} consultation visits{careDoctor!=="all"?` for ${careDoctor==="doctor-lim"?"Dr. Lim":"Dr. Anita"}`:""}{careDate?` on ${careDate} (Malaysia time)`:""}{careSearchTerm?" matching your search":""}{careFilter==="checkout"?" ready for checkout":careFilter==="dispensing"?" awaiting dispensing":careFilter==="billing"?" awaiting a bill":careFilter==="unpaid"?" with unpaid bills":""}. Refreshes every three seconds.</p></section>:null}
    {staff&&!loading?<section aria-label="Staff care sorting" className="panel mb-6">
      <label className="block text-sm font-semibold">Visit order<select className="mt-2" disabled={busy} value={careSort} onChange={e=>{setCareSort(e.target.value as typeof careSort);setDispensing("");setBillReview(null);setPaymentReview("");setError("");}}><option value="newest">Newest visit first</option><option value="oldest">Oldest visit first</option></select></label>
      <p className="muted mt-2 text-sm">Orders by scheduled visit time. Filters and workload counts stay the same.</p>
    </section>:null}
    {staff&&!loading?<section aria-label="Staff workload summary" className="panel mb-6">
      <h2 className="text-lg font-semibold">Staff workload</h2>
      <p className="muted mt-2 text-sm">Counts follow the patient search, doctor and date above, across all work statuses. Ready for checkout means the doctor has finished and staff have not completed the visit. A visit can need more than one step. Choose a count to filter the care list.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{workload.map(({filter,label})=><button key={filter} className={`btn ${careFilter===filter?"":"secondary"} flex flex-col gap-2`} disabled={busy} aria-label={`${label}: ${scopedVisits.filter(record=>matchesWork(record,filter)).length} visits`} aria-pressed={careFilter===filter} onClick={()=>selectCareFilter(filter)}><span>{label}</span><strong className="text-2xl">{scopedVisits.filter(record=>matchesWork(record,filter)).length}</strong></button>)}</div>
    </section>:null}
    {staff&&!loading&&checkoutTarget?<section aria-label="Returned checkout visit" className="panel mb-6"><h2 className="font-semibold">Returned from patient queue</h2><p className="mt-2 text-sm">{visits.some(r=>r.visit.id===checkoutTarget.visit)?"The checkout visit is highlighted below. Continue with its dispensing and billing actions.":"The linked visit is not in the current care list. Reset filters to view other visits, or return to the patient queue to check its status."}</p></section>:null}
    {error && <div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div>}
    {notice && <div role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</div>}
    {loading && <p className="muted">Loading saved visits…</p>}
    {!loading&&visits.length===0&&<div className="panel"><h2 className="font-semibold">{staff&&consultationVisits.length>0?(careDoctor!=="all"?"No visits match the selected doctor and care filters.":careDate?"No visits match the selected date and care filters.":careSearchTerm?"No visits match your search and care-list filter.":careFilter==="checkout"?"No visits ready for checkout.":careFilter==="dispensing"?"No prescriptions awaiting dispensing.":careFilter==="billing"?"No completed visits awaiting a bill.":"No unpaid bills."):"No consultation visits yet"}</h2><p className="muted mt-2">{staff&&consultationVisits.length>0?(careDoctor!=="all"?"Choose All doctors or adjust the date, search and care-list filter.":careDate?"Choose All dates, clear search or change the care-list filter.":careSearchTerm?"Clear search or choose a different care-list filter.":"Choose All to view the other consultation visits."):"Book and call a patient from the queue, then choose the assigned doctor here."}</p></div>}
    <div className="grid gap-6">{visits.map(({ visit, prescription, invoice }) => <section key={visit.id} className={`panel ${staff&&checkoutTarget?.visit===visit.id?"outline outline-2 outline-[#176f5e]":""}`}>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">{queueToken(visit)} · {visit.patient_name}</h2><p className="muted mt-1 text-sm">{visit.doctor_name} · {visitTime(visit.starts_at)}</p></div><span className="badge">{visit.status}</span></div>
      {staff ? <CheckoutChecklist record={{visit,prescription,invoice}} /> : null}
      <div className="grid gap-6 md:grid-cols-2"><div><h3 className="mb-3 font-semibold">Prescription</h3>
        {prescription ? <><span className="badge">{prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing"}</span><ul className="my-4 space-y-3">{prescription.items.map(item => <li key={item.medicine_id}><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="muted text-sm">{item.directions}</p></li>)}</ul>{staff&&prescription.status==="dispensed"?<DispensingHistory api={api} prescription={prescription}/>:null}{staff && prescription.status === "issued" && (dispensing===prescription.id?<DispensingReview api={api} record={{visit,prescription,invoice}} catalog={catalog} busy={busy} onConfirm={allocations=>confirmDispensing({visit,prescription,invoice},allocations)} onCancel={()=>{setDispensing("");setError("");}}/>:<button className="btn" disabled={busy} onClick={()=>{setDispensing(prescription.id);setError("");}}>Review dispensing</button>)}</> : <>
          <p className="muted mb-3 text-sm">No prescription issued.{visit.consultation_finished_at ? " The doctor has finished this consultation; a new prescription cannot be added." : invoice ? " This visit has been billed; new items cannot be added." : " Issue before generating a bill if items are needed."}</p>
          {!staff && !invoice && !visit.consultation_finished_at && selected !== visit.id && <button className="btn" disabled={busy} onClick={() => { setSelected(visit.id); setReview(null); setQuantities({}); setMedicineSearch(""); setDirections("Demo instructions only — not medical advice."); setError(""); }}>Create prescription</button>}
          {!staff && !visit.consultation_finished_at && selected === visit.id && <div className="rounded-xl bg-[#f4f7f6] p-4">{!staff&&visit.doctor_id===actor?<PrescribingBackground key={visit.id} api={api} actor={actor} visit={visit} busy={busy}/>:null}<fieldset disabled={busy||!!review}><p className="muted mb-3 text-sm">Issued items are fixed for this demo. Check quantities before saving.</p><label className="mb-3 block text-sm">Search prescription medicines<input type="search" disabled={busy} maxLength={100} value={medicineSearch} onChange={e=>setMedicineSearch(e.target.value)} placeholder="Name, strength or form" className="mt-2 w-full rounded-lg border border-[#ccdcd4] bg-white p-2"/></label><button className="btn secondary mb-3" disabled={busy||!medicineSearch} onClick={()=>setMedicineSearch("")}>Clear medicine search</button><p role="status" className="muted mb-3 text-sm">Showing {visibleCatalog.length} of {catalog.length} active medicines. Search keeps selected quantities.</p>{chosenItems.length?<div className="mb-3 rounded-lg border border-[#ccdcd4] bg-white p-3"><h4 className="font-semibold">Selected medicines ({chosenItems.length})</h4><ul className="mt-2 space-y-2">{chosenItems.map(([id,quantity])=>{const medicine=catalog.find(m=>m.id===id);return <li key={id}>{medicine?medicineLabel(medicine):"Unavailable medicine — cancel and reopen to review"} × {quantity}</li>;})}</ul></div>:<p className="muted mb-3 text-sm">No medicines selected yet.</p>}{visibleCatalog.length===0?<p className="mb-3 text-sm">{searchTerm?"No active medicines match your search. Clear search to view all choices.":"No active medicines available."}</p>:null}{visibleCatalog.map(m => <label key={m.id} className="mb-3 block text-sm">{medicineLabel(m)} · {money(m.price_cents)} · {m.stock} in stock<input aria-label={`Quantity ${m.id}`} className="mt-2 block w-full rounded-lg border border-[#ccdcd4] bg-white p-2" type="number" min="0" max="20" step="1" disabled={busy} value={quantities[m.id] || "0"} onChange={e => setQuantities(q => ({ ...q, [m.id]: e.target.value }))} /></label>)}<label className="block text-sm">Demo directions<textarea className="mt-2 w-full rounded-lg border border-[#ccdcd4] p-2" maxLength={300} disabled={busy} value={directions} onChange={e => setDirections(e.target.value)} /></label></fieldset>{review&&review.visitId===visit.id?<section aria-label="Prescription review" className="mt-4 rounded-lg border border-[#ccdcd4] bg-white p-4"><h4 className="font-semibold">Review prescription</h4><p className="my-3">{queueToken(visit)} · {visit.patient_name} · {visit.doctor_name} · {visitTime(visit.starts_at)}</p><ul className="my-3 space-y-3">{review.items.map(item=><li key={item.medicine_id}><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="whitespace-pre-wrap break-words text-sm">{item.directions}</p></li>)}</ul><p className="muted my-3 text-sm">Confirming saves these quantities and directions as a fixed prescription. Staff will check stock when dispensing.</p>{reviewChanged?<p role="alert" className="my-3 text-red-800">Medicine details changed. Keep editing and review the current choices again.</p>:null}<div className="flex flex-wrap gap-3"><button className="btn" disabled={busy||reviewChanged} onClick={()=>confirmPrescription(visit.id)}>{busy?"Saving…":"Confirm issue prescription"}</button><button className="btn secondary" disabled={busy} onClick={()=>{setReview(null);setError("");}}>Keep editing prescription</button><button className="btn secondary" disabled={busy} onClick={()=>{setReview(null);setSelected("");setError("");}}>Cancel prescription</button></div></section>:<div className="mt-4 flex flex-wrap gap-3"><button className="btn" disabled={busy} onClick={() => reviewPrescription(visit.id)}>Review prescription</button><button className="btn secondary" disabled={busy} onClick={() => setSelected("")}>Cancel</button></div>}</div>}
        </>}
      </div><div><h3 className="mb-3 font-semibold">Bill · simulation</h3>{invoice ? <><ul className="space-y-3">{invoice.lines.map((line, i) => <li key={i} className="flex justify-between gap-3 text-sm"><span>{line.description} × {line.quantity}</span><strong>{money(line.unit_price_cents * line.quantity)}</strong></li>)}</ul><div className="my-4 flex items-center justify-between border-t border-[#dce6e0] pt-4"><strong>Total {money(invoice.total_cents)}</strong><span className="badge">{invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}</span></div>{staff && invoice.status === "unpaid" && (paymentReview===invoice.id?<PaymentReview record={{visit,prescription,invoice}} busy={busy} onConfirm={()=>confirmPayment({visit,prescription,invoice})} onCancel={()=>{setPaymentReview("");setError("");}}/>:<button className="btn" disabled={busy || (!!prescription && prescription.status !== "dispensed")} onClick={()=>{setPaymentReview(invoice.id);setError("");}}>Review simulated payment</button>)}{invoice.status === "paid" && <><p className="muted text-sm">Demo receipt {invoice.id.slice(0, 8)} · {invoice.paid_at ? visitTime(invoice.paid_at) : ""}</p>{staff?<button className="btn secondary mt-3" disabled={busy} onClick={()=>setReceipt({visit,prescription,invoice})}>View simulated receipt</button>:null}</>}{prescription?.status === "issued" && <p className="muted mt-3 text-sm">Dispense before recording payment.</p>}</> : <><p className="muted mb-3 text-sm">Complete the visit, then generate a fixed itemised bill. Demo consultation: RM 30.00.</p>{staff && (billReview?.visitId===visit.id?<BillReview record={{visit,prescription,invoice}} lines={billReview.lines} changed={billReviewChanged} busy={busy} onConfirm={()=>confirmBill({visit,prescription,invoice})} onCancel={()=>{setBillReview(null);setError("");}}/>:<button className="btn" disabled={busy || visit.status !== "completed"} onClick={()=>reviewBill({visit,prescription,invoice})}>Review bill</button>)}</>}</div></div>
    </section>)}</div>
  </main>;
}
