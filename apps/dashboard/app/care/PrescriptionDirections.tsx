"use client";
import { useEffect, useState } from "react";
import { Care, DemoActor, DemoApi, Prescription, PrescriptionDirectionsHistory, medicineLabel, visitTime } from "@smart-skin/shared";

type Draft = { version: number; directions: Record<string, string>; reason: string; review: boolean };

export default function PrescriptionDirections({ api, actor, record, busy, onBusy, onSaved }: {
  api: DemoApi; actor: DemoActor; record: Care; busy: boolean; onBusy: (value: boolean) => void; onSaved: (prescription: Prescription) => void;
}) {
  const { visit, prescription, invoice } = record;
  const allowed = actor.startsWith("doctor-") && visit.doctor_id === actor;
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<PrescriptionDirectionsHistory | null>(null);
  const [historyError, setHistoryError] = useState("");
  const [historyRefresh, setHistoryRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    if (!allowed || !prescription || !showHistory) return () => { active = false; };
    setHistory(null); setHistoryError("");
    void api.prescriptionDirectionsHistory(visit.id).then(data => { if (active) setHistory(data); })
      .catch(e => { if (active) setHistoryError(e instanceof Error ? e.message : "Cannot load directions history."); });
    return () => { active = false; };
  }, [api, allowed, visit.id, prescription?.version, showHistory, historyRefresh]);
  if (!allowed || !prescription) return null;
  const eligible = visit.status === "called" && !visit.consultation_finished_at && prescription.status === "issued" && !invoice && !!prescription.version;
  const changed = !!draft && draft.version !== prescription.version;
  const items = prescription.items.map(item => ({ medicine_id: item.medicine_id, directions: (draft?.directions[item.medicine_id] ?? item.directions).trim() }));
  function start() {
    setError(""); setDraft({ version: prescription!.version!, directions: Object.fromEntries(prescription!.items.map(item => [item.medicine_id, item.directions])), reason: "", review: false });
  }
  function review() {
    if (!draft || busy || !eligible || changed) return;
    if (!draft.reason.trim() || items.some(item => !item.directions || item.directions.length > 300)) { setError("Enter a correction reason and nonblank directions for each item, within 300 characters."); return; }
    if (items.every(item => item.directions === prescription!.items.find(saved => saved.medicine_id === item.medicine_id)!.directions)) { setError("Change at least one direction before reviewing."); return; }
    setError(""); setDraft({ ...draft, reason: draft.reason.trim(), review: true });
  }
  async function save() {
    if (!draft?.review || busy || !eligible || changed) return;
    onBusy(true); setError("");
    try {
      const saved = await api.correctPrescriptionDirections(visit.id, draft.version, draft.reason, items);
      onSaved(saved); setDraft(null); setHistoryRefresh(value => value + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "Cannot save corrected directions."); }
    finally { onBusy(false); }
  }
  return <section aria-label="Prescription directions corrections" className="my-4 rounded-xl border border-[#ccdcd4] p-4">
    <h4 className="font-semibold">Directions corrections · revision {prescription.version ?? 1}</h4>
    {!draft ? <>{eligible ? <button className="btn secondary mt-3" disabled={busy} onClick={start}>Correct directions</button> : <p className="muted mt-2 text-sm">Directions can be corrected while the consultation is open, before handover, dispensing or billing.</p>}</> : <>
      <p className="muted my-3 text-sm">Medicines, quantities and saved prices stay fixed. A reason and confirmation are required; previous directions remain in history.</p>
      {!eligible || changed ? <p role="alert" className="my-3 text-red-800">This visit or prescription changed. Cancel and reopen to review its latest state.</p> : null}
      {error ? <p role="alert" className="my-3 text-red-800">{error}</p> : null}
      {draft.review ? <section aria-label="Directions correction review" className="my-3 rounded-lg bg-[#f4f7f6] p-3">
        <h5 className="font-semibold">Review directions correction</h5>
        {prescription.items.map(item => <div key={item.medicine_id} className="my-3 text-sm"><strong>{medicineLabel(item)} × {item.quantity}</strong><p className="mt-1 whitespace-pre-wrap break-words">Previous: {item.directions}</p><p className="mt-1 whitespace-pre-wrap break-words">Corrected: {draft.directions[item.medicine_id].trim()}</p></div>)}
        <p className="whitespace-pre-wrap break-words text-sm">Reason: {draft.reason}</p>
        <div className="mt-4 flex flex-wrap gap-3"><button className="btn" disabled={busy || changed || !eligible} onClick={save}>{busy ? "Saving…" : "Confirm directions correction"}</button><button className="btn secondary" disabled={busy} onClick={() => setDraft({ ...draft, review: false })}>Keep editing directions</button></div>
      </section> : <fieldset disabled={busy || changed || !eligible}>
        {prescription.items.map(item => <label key={item.medicine_id} className="my-3 block text-sm font-semibold">{medicineLabel(item)} × {item.quantity}<textarea aria-label={`Corrected directions ${item.medicine_id}`} maxLength={300} className="mt-2 w-full rounded-lg border border-[#ccdcd4] p-2 font-normal" value={draft.directions[item.medicine_id]} onChange={event => setDraft({ ...draft, directions: { ...draft.directions, [item.medicine_id]: event.target.value } })}/></label>)}
        <label className="my-3 block text-sm font-semibold">Correction reason<textarea maxLength={300} className="mt-2 w-full rounded-lg border border-[#ccdcd4] p-2 font-normal" value={draft.reason} onChange={event => setDraft({ ...draft, reason: event.target.value })}/></label>
        <button className="btn" onClick={review}>Review directions correction</button>
      </fieldset>}
      <button className="btn secondary mt-3" disabled={busy} onClick={() => { setDraft(null); setError(""); }}>Cancel directions correction</button>
    </>}
    <button className="mt-4 block text-sm font-semibold underline" disabled={busy} onClick={() => setShowHistory(value => !value)}>{showHistory ? "Hide directions history" : "View directions history"}</button>
    {showHistory ? <section aria-label="Prescription directions history" className="mt-3 border-t border-[#dce6e0] pt-3">
      {historyError ? <p role="alert" className="text-red-800">{historyError}</p> : !history ? <p>Loading directions history…</p> : !history.revisions.length ? <p className="muted text-sm">No directions corrections recorded.</p> : history.revisions.map(revision => <article key={revision.id} className="my-3 rounded-lg bg-[#f4f7f6] p-3 text-sm">
        <h5 className="font-semibold">Revision {revision.version} · {visitTime(revision.created_at)} · {revision.doctor_name}</h5>
        <p className="my-2 whitespace-pre-wrap break-words">Reason: {revision.reason}</p>
        {revision.directions.map(item => <div key={item.medicine_id} className="my-2"><strong>{medicineLabel(prescription.items.find(saved => saved.medicine_id === item.medicine_id)!)}</strong><p className="whitespace-pre-wrap break-words">Previous: {revision.previous_directions.find(saved => saved.medicine_id === item.medicine_id)?.directions}</p><p className="whitespace-pre-wrap break-words">Corrected: {item.directions}</p></div>)}
      </article>)}
      <button className="mt-2 text-sm underline" disabled={busy} onClick={() => setHistoryRefresh(value => value + 1)}>Refresh directions history</button>
    </section> : null}
  </section>;
}
