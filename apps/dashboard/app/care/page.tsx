"use client";
import { useEffect, useMemo, useState } from "react";
import { Care, DemoActor, DemoApi, Medicine, PrescriptionItem, medicineLabel, money, queueToken, visitTime } from "@smart-skin/shared";

const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function CarePage() {
  const [actor, setActor] = useState<DemoActor>("doctor-lim");
  const api = useMemo(() => new DemoApi(base, actor), [actor]);
  const [records, setRecords] = useState<Care[]>([]);
  const [catalog, setCatalog] = useState<Medicine[]>([]);
  const [selected, setSelected] = useState("");
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [directions, setDirections] = useState("Demo instructions only — not medical advice.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const staff = actor === "staff-demo";
  useEffect(() => {
    let active = true, fetching = false;
    setRecords([]); setCatalog([]); setSelected(""); setQuantities({}); setNotice(""); setError(""); setLoading(true);
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
      await fn(); setSelected("");
      const [care, medicines] = await Promise.all([api.care(), api.medicines()]);
      setRecords(care); setCatalog(medicines); setNotice(message);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save. Refresh before retrying."); }
    finally { setBusy(false); }
  }
  function issue(visitId: string) {
    if (Object.values(quantities).some(q => !Number.isInteger(Number(q)) || Number(q) < 0 || Number(q) > 20)) { setError("Quantities must be whole numbers from 0 to 20. Zero leaves an item out."); return; }
    if(Object.entries(quantities).some(([id,value])=>Number(value)>0&&!catalog.some(item=>item.id===id))){setError("A selected medicine is no longer active. Cancel and reopen the prescription to review current choices.");return;}
    const items: PrescriptionItem[] = catalog.filter(m => Number(quantities[m.id]) > 0).map(m => ({ medicine_id: m.id, quantity: Number(quantities[m.id]), directions: directions.trim() }));
    if (!items.length || !directions.trim() || items.some(i => !Number.isInteger(i.quantity) || i.quantity > 20)) { setError("Select at least one item with a whole quantity from 1 to 20 and enter demo directions."); return; }
    void action(() => api.prescribe(visitId, items), "Prescription issued. Staff and patient can see the saved items.");
  }
  const visits = records.filter(r => r.visit.status === "called" || r.visit.status === "completed");
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Visit care & billing</p></div><nav className="flex flex-wrap gap-3">{staff?<a className="btn secondary" href="/stock">Stock</a>:null}<a className="btn secondary" href="/consultations">Consultation notes</a><a className="btn secondary" href="/reviews">Doctor reviews</a><a className="btn secondary" href="/">← Patient queue</a></nav></header>
    <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Synthetic demonstration. Demo identities are not secure login. Items are placeholders, not medication. All prices and payments are simulated; no money moves.</div>
    <h1 className="mb-2 text-3xl font-semibold">From consultation to checkout.</h1><p className="muted mb-6">Doctor issues → staff dispenses → completed visit is billed → simulated payment.</p>
    <section className="panel mb-6"><label className="text-sm font-semibold">Demo role<select className="mt-2" disabled={busy} value={actor} onChange={e => setActor(e.target.value as DemoActor)}><option value="doctor-lim">Dr. Lim (demo)</option><option value="doctor-anita">Dr. Anita (demo)</option><option value="staff-demo">Staff Demo — dispensing & billing</option></select></label><p className="muted mt-3 text-sm">{staff ? "Staff view operational prescription and bill details." : "Doctors see only their assigned visits. Call a patient from the queue before issuing."}</p></section>
    {error && <div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div>}
    {notice && <div role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</div>}
    {loading && <p className="muted">Loading saved visits…</p>}
    {!loading && visits.length === 0 && <div className="panel"><h2 className="font-semibold">No consultation visits yet</h2><p className="muted mt-2">Book and call a patient from the queue, then choose the assigned doctor here.</p></div>}
    <div className="grid gap-6">{visits.map(({ visit, prescription, invoice }) => <section key={visit.id} className="panel">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">{queueToken(visit)} · {visit.patient_name}</h2><p className="muted mt-1 text-sm">{visit.doctor_name} · {visitTime(visit.starts_at)}</p></div><span className="badge">{visit.status}</span></div>
      <div className="grid gap-6 md:grid-cols-2"><div><h3 className="mb-3 font-semibold">Prescription</h3>
        {prescription ? <><span className="badge">{prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing"}</span><ul className="my-4 space-y-3">{prescription.items.map(item => <li key={item.medicine_id}><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="muted text-sm">{item.directions}</p></li>)}</ul>{staff && prescription.status === "issued" && <button className="btn" disabled={busy} onClick={() => action(() => api.dispense(prescription.id), "Dispensing saved. Stock deducted once.")}>Confirm dispensing</button>}</> : <>
          <p className="muted mb-3 text-sm">No prescription issued.{invoice ? " This visit has been billed; new items cannot be added." : " Issue before generating a bill if items are needed."}</p>
          {!staff && !invoice && selected !== visit.id && <button className="btn" disabled={busy} onClick={() => { setSelected(visit.id); setQuantities({}); setDirections("Demo instructions only — not medical advice."); setError(""); }}>Create prescription</button>}
          {!staff && selected === visit.id && <div className="rounded-xl bg-[#f4f7f6] p-4"><p className="muted mb-3 text-sm">Issued items are fixed for this demo. Check quantities before saving.</p>{catalog.map(m => <label key={m.id} className="mb-3 block text-sm">{medicineLabel(m)} · {money(m.price_cents)} · {m.stock} in stock<input aria-label={`Quantity ${m.id}`} className="mt-2 block w-full rounded-lg border border-[#ccdcd4] bg-white p-2" type="number" min="0" max="20" step="1" disabled={busy} value={quantities[m.id] || "0"} onChange={e => setQuantities(q => ({ ...q, [m.id]: e.target.value }))} /></label>)}<label className="block text-sm">Demo directions<textarea className="mt-2 w-full rounded-lg border border-[#ccdcd4] p-2" maxLength={300} disabled={busy} value={directions} onChange={e => setDirections(e.target.value)} /></label><div className="mt-4 flex flex-wrap gap-3"><button className="btn" disabled={busy} onClick={() => issue(visit.id)}>{busy ? "Saving…" : "Issue prescription"}</button><button className="btn secondary" disabled={busy} onClick={() => setSelected("")}>Cancel</button></div></div>}
        </>}
      </div><div><h3 className="mb-3 font-semibold">Bill · simulation</h3>{invoice ? <><ul className="space-y-3">{invoice.lines.map((line, i) => <li key={i} className="flex justify-between gap-3 text-sm"><span>{line.description} × {line.quantity}</span><strong>{money(line.unit_price_cents * line.quantity)}</strong></li>)}</ul><div className="my-4 flex items-center justify-between border-t border-[#dce6e0] pt-4"><strong>Total {money(invoice.total_cents)}</strong><span className="badge">{invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}</span></div>{staff && invoice.status === "unpaid" && <button className="btn" disabled={busy || (!!prescription && prescription.status !== "dispensed")} onClick={() => action(() => api.paySimulated(invoice.id), "Simulated payment saved. No money was transferred.")}>Record simulated payment</button>}{invoice.status === "paid" && <p className="muted text-sm">Demo receipt {invoice.id.slice(0, 8)} · {invoice.paid_at ? visitTime(invoice.paid_at) : ""}</p>}{prescription?.status === "issued" && <p className="muted mt-3 text-sm">Dispense before recording payment.</p>}</> : <><p className="muted mb-3 text-sm">Complete the visit, then generate a fixed itemised bill. Demo consultation: RM 30.00.</p>{staff && <button className="btn" disabled={busy || visit.status !== "completed"} onClick={() => action(() => api.invoice(visit.id), "Itemised demo bill saved. Patient can now view it.")}>Generate bill</button>}</>}</div></div>
    </section>)}</div>
  </main>;
}
