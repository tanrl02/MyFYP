"use client";
import AssessmentResult from "../components/AssessmentResult";
import { useEffect, useMemo, useState } from "react";
import { AssessmentShare, DemoApi, DemoDoctor, ReviewDraft, doctorNames, queueToken, visitTime } from "@smart-skin/shared";

const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function ReviewsPage() {
  const [doctor, setDoctor] = useState<DemoDoctor>("doctor-lim");
  const [busy,setBusy]=useState(false);
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Doctor assessment review</p></div><nav className="flex gap-3"><a className="btn secondary" href="/">Patient queue</a><a className="btn secondary" href="/care">Prescriptions & billing</a></nav></header>
    <div className="mb-7 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Demo identities only. Use fictional review text. New AI suggestions are experimental and may be wrong; earlier records remain simulations. Review each photo independently.</div>
    <h1 className="text-3xl font-semibold">Shared assessments</h1><p className="muted my-3">Patients choose which assessment to share with you. Revoked shares leave your inbox.</p>
    <label className="panel my-6 block max-w-md text-sm font-semibold">Doctor demo identity<select className="mt-2" value={doctor} disabled={busy} onChange={e => setDoctor(e.target.value as DemoDoctor)}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id => <option key={id} value={id}>{doctorNames[id]}</option>)}</select></label>
    <ReviewInbox key={doctor} doctor={doctor} onBusy={setBusy} />
  </main>;
}

function ReviewInbox({ doctor,onBusy }: { doctor: DemoDoctor;onBusy:(busy:boolean)=>void }) {
  const api = useMemo(() => new DemoApi(base, doctor), [doctor]);
  const [shares, setShares] = useState<AssessmentShare[]>([]), [detail, setDetail] = useState<AssessmentShare | null>(null);
  const [note, setNote] = useState(""), [followUp, setFollowUp] = useState("");
  const [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [selected, setSelected] = useState("");
  const [savedDraft,setSavedDraft]=useState<ReviewDraft|null>(null);
  useEffect(()=>{onBusy(busy);return()=>onBusy(false);},[busy,onBusy]);
  useEffect(() => {
    let active = true, fetching = false;
    async function load() {
      if (fetching || busy) return; fetching = true;
      try {
        const data = await api.shares();
        // Reload an open detail too: revoke must clear an already displayed photo.
        const opened = selected && data.some(s => s.id === selected) ? await api.sharedAssessment(selected) : null;
        if (active) { setShares(data); setDetail(opened); if (selected && !opened) { setSelected(""); setConfirm(false); setNote(""); setFollowUp(""); setSavedDraft(null); setNotice("Patient access was revoked. The assessment is no longer available."); } setError(""); }
      } catch (e) { if (active) { setDetail(null); setError(e instanceof Error ? e.message : "Cannot load shared assessments."); } }
      finally { fetching = false; if (active) setLoading(false); }
    }
    void load(); const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [api, selected,busy]);
  async function open(id: string) {
    if (busy) return; setBusy(true); setError(""); setNotice(""); setConfirm(false); setDetail(null); setSavedDraft(null);
    try { const data = await api.sharedAssessment(id); const draft=data.review?null:await api.reviewDraft(id); setDetail(data); setSelected(id); setSavedDraft(draft); setNote(draft?.note||""); setFollowUp(draft?.follow_up||""); }
    catch (e) { setError(e instanceof Error ? e.message : "Assessment is unavailable."); setSelected(""); }
    finally { setBusy(false); }
  }
  async function saveDraft() {
    if(!detail||busy||!savedDraft)return;setBusy(true);setError("");setNotice("");
    try{const saved=await api.saveReviewDraft(detail.id,note.trim(),followUp.trim(),savedDraft.version);setSavedDraft(saved);setNote(saved.note);setFollowUp(saved.follow_up);setNotice("Private draft saved. The patient cannot see it and no notification was sent.");}
    catch(e){setError(e instanceof Error?e.message:"Cannot save draft.");}finally{setBusy(false);}
  }
  async function publish() {
    if (!detail || busy) return; setBusy(true); setError("");
    try {
      const saved = await api.publishReview(detail.id, note.trim(), followUp.trim(),savedDraft?.version);
      setShares(current => current.map(s => s.id === saved.id ? saved : s));
      setDetail(current => current ? { ...saved, assessment: current.assessment } : null); setConfirm(false); setSavedDraft(null); setNotice("Review published. The patient can now read it.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to publish. Refresh before retrying."); }
    finally { setBusy(false); }
  }
  return <>
    {error ? <div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div> : null}
    {notice ? <p role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</p> : null}
    {loading ? <p className="muted">Loading shared assessments…</p> : null}
    <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]">
      <section className="panel"><h2 className="mb-4 text-lg font-semibold">Your inbox · {shares.length}</h2><p className="muted mb-4 text-xs">Latest 100 active shares. Refreshes every five seconds.</p>
        {shares.map(share => <button key={share.id} disabled={busy} aria-label={`Open shared assessment ${share.id.slice(0,8)}`} onClick={() => open(share.id)} className={`mb-3 block w-full rounded-xl border p-4 text-left ${selected === share.id ? "border-[#176f5e] bg-[#edf4f1]" : "border-[#dce6e0]"}`}><strong className="block">{share.patient_name}</strong><span className="muted mt-2 block text-xs">Shared {visitTime(share.created_at)}</span><span className="muted mt-2 block text-xs">{share.visit ? `Appointment ${queueToken(share.visit)} · ${visitTime(share.visit.starts_at)}` : "Direct doctor share"}</span><span className="badge mt-3 inline-block">{share.review ? "Reviewed" : "Awaiting review"}</span></button>)}
        {!loading && !shares.length ? <p className="muted">No active assessments shared with this doctor.</p> : null}
      </section>
      <section className="panel">{detail ? <>
        <h2 className="text-xl font-semibold">{detail.patient_name} · assessment</h2><p className="muted mt-2 text-sm">Saved {detail.assessment ? visitTime(detail.assessment.created_at) : ""}</p>
        {detail.visit ? <p className="my-3 rounded-xl bg-[#edf4f1] p-3 text-sm">Linked appointment: {queueToken(detail.visit)} · {detail.visit.doctor_name} · {visitTime(detail.visit.starts_at)} · {detail.visit.status}</p> : <p className="muted mt-3 text-sm">Direct doctor share · no appointment linked</p>}
        {detail.assessment?.photo_uri ? <img alt="Patient-shared assessment photo" src={detail.assessment.photo_uri} className="my-5 max-h-80 w-full rounded-xl bg-[#f4f7f6] object-contain" /> : null}
        {detail.assessment?<AssessmentResult assessment={detail.assessment}/>:null}
        <h3 className="font-semibold">Patient message</h3><p className="muted my-3 whitespace-pre-wrap">{detail.patient_message || "No message provided."}</p>
        {detail.review ? <div className="mt-5 border-t border-[#dce6e0] pt-5"><h3 className="font-semibold">Published doctor review · demo</h3><p className="muted my-3 whitespace-pre-wrap">{detail.review.note}</p><h3 className="font-semibold">Follow-up</h3><p className="muted my-3 whitespace-pre-wrap">{detail.review.follow_up}</p><p className="muted text-xs">Published {visitTime(detail.review.created_at)} · saved reviews cannot be replaced.</p></div> : <div className="mt-5 border-t border-[#dce6e0] pt-5">
          <h3 className="mb-4 font-semibold">Write a review</h3><p className="muted mb-3 text-sm">Private draft: only this doctor can reopen it while patient access remains active. Save before leaving this screen.</p>{savedDraft?.updated_at?<p className="muted mb-3 text-sm">Draft saved {visitTime(savedDraft.updated_at)}{note.trim()!==savedDraft.note||followUp.trim()!==savedDraft.follow_up?" · Unsaved changes":""}</p>:null}<label className="block text-sm">Review note<textarea aria-label="Review note" className="my-2 block min-h-32 w-full rounded-lg border border-[#ccdcd4] p-3" maxLength={2000} disabled={busy || confirm} value={note} onChange={e => setNote(e.target.value)} placeholder="Fictional observations for demonstration." /></label>
          <label className="block text-sm">Follow-up<textarea aria-label="Follow-up" className="my-2 block min-h-20 w-full rounded-lg border border-[#ccdcd4] p-3" maxLength={1000} disabled={busy || confirm} value={followUp} onChange={e => setFollowUp(e.target.value)} placeholder="Fictional next step for demonstration." /></label>
          {!confirm?<div className="mt-4 flex flex-wrap gap-3"><button className="btn secondary" disabled={busy||!savedDraft||(note.trim()===savedDraft.note&&followUp.trim()===savedDraft.follow_up)} onClick={saveDraft}>{busy?"Saving…":"Save draft"}</button><button className="underline" disabled={busy} onClick={()=>open(detail.id)}>Reload saved draft</button></div>:null}
          {confirm ? <div className="mt-4 rounded-xl bg-[#f4f7f6] p-4"><p className="mb-4 text-sm">Publish this note and follow-up to {detail.patient_name}? The patient can read it immediately. Published reviews are fixed in this demo.</p><button className="btn" disabled={busy} onClick={publish}>{busy ? "Publishing…" : "Confirm publish"}</button><button className="btn secondary ml-3" disabled={busy} onClick={() => setConfirm(false)}>Keep editing</button></div> : <button className="btn mt-4" disabled={busy || !note.trim() || !followUp.trim()} onClick={() => setConfirm(true)}>Publish review</button>}
          <p className="muted mt-4 text-xs">Only saved drafts survive reloads or changing doctor/assessment. Reload saved draft discards unsaved changes. Publishing makes the confirmed text visible to the patient and closes draft editing. Reviews do not issue prescriptions or change appointment status.</p>
        </div>}
      </> : <><h2 className="font-semibold">Choose a shared assessment</h2><p className="muted mt-3">Open an inbox entry to view the patient's photo, message and published review.</p></>}</section>
    </div>
  </>;
}
