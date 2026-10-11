"use client";
import { useEffect, useMemo, useState } from "react";
import { AssessmentShare, DemoApi, DemoDoctor, doctorNames, queueToken, visitTime } from "@smart-skin/shared";

const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function ReviewsPage() {
  const [doctor, setDoctor] = useState<DemoDoctor>("doctor-lim");
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Doctor assessment review</p></div><nav className="flex gap-3"><a className="btn secondary" href="/">Patient queue</a><a className="btn secondary" href="/care">Prescriptions & billing</a></nav></header>
    <div className="mb-7 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Demo identities only. Use fictional review text. AI results are fixed simulations; no image analysis or diagnosis was performed.</div>
    <h1 className="text-3xl font-semibold">Shared assessments</h1><p className="muted my-3">Patients choose which assessment to share with you. Revoked shares leave your inbox.</p>
    <label className="panel my-6 block max-w-md text-sm font-semibold">Doctor demo identity<select className="mt-2" value={doctor} onChange={e => setDoctor(e.target.value as DemoDoctor)}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id => <option key={id} value={id}>{doctorNames[id]}</option>)}</select></label>
    <ReviewInbox key={doctor} doctor={doctor} />
  </main>;
}

function ReviewInbox({ doctor }: { doctor: DemoDoctor }) {
  const api = useMemo(() => new DemoApi(base, doctor), [doctor]);
  const [shares, setShares] = useState<AssessmentShare[]>([]), [detail, setDetail] = useState<AssessmentShare | null>(null);
  const [note, setNote] = useState(""), [followUp, setFollowUp] = useState("");
  const [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [selected, setSelected] = useState("");
  useEffect(() => {
    let active = true, fetching = false;
    async function load() {
      if (fetching) return; fetching = true;
      try {
        const data = await api.shares();
        // Reload an open detail too: revoke must clear an already displayed photo.
        const opened = selected && data.some(s => s.id === selected) ? await api.sharedAssessment(selected) : null;
        if (active) { setShares(data); setDetail(opened); if (selected && !opened) { setSelected(""); setConfirm(false); setNote(""); setFollowUp(""); setNotice("Patient access was revoked. The assessment is no longer available."); } setError(""); }
      } catch (e) { if (active) { setDetail(null); setError(e instanceof Error ? e.message : "Cannot load shared assessments."); } }
      finally { fetching = false; if (active) setLoading(false); }
    }
    void load(); const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [api, selected]);
  async function open(id: string) {
    if (busy) return; setBusy(true); setError(""); setNotice(""); setConfirm(false); setDetail(null);
    try { const data = await api.sharedAssessment(id); setDetail(data); setSelected(id); setNote(""); setFollowUp(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Assessment is unavailable."); setSelected(""); }
    finally { setBusy(false); }
  }
  async function publish() {
    if (!detail || busy) return; setBusy(true); setError("");
    try {
      const saved = await api.publishReview(detail.id, note.trim(), followUp.trim());
      setShares(current => current.map(s => s.id === saved.id ? saved : s));
      setDetail(current => current ? { ...saved, assessment: current.assessment } : null); setConfirm(false); setNotice("Review published. The patient can now read it.");
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
        <div className="my-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900"><strong>AI result · SIMULATION</strong><p className="mt-2">{detail.assessment?.example_category}</p><p>{detail.assessment?.message}</p></div>
        <h3 className="font-semibold">Patient message</h3><p className="muted my-3 whitespace-pre-wrap">{detail.patient_message || "No message provided."}</p>
        {detail.review ? <div className="mt-5 border-t border-[#dce6e0] pt-5"><h3 className="font-semibold">Published doctor review · demo</h3><p className="muted my-3 whitespace-pre-wrap">{detail.review.note}</p><h3 className="font-semibold">Follow-up</h3><p className="muted my-3 whitespace-pre-wrap">{detail.review.follow_up}</p><p className="muted text-xs">Published {visitTime(detail.review.created_at)} · saved reviews cannot be replaced.</p></div> : <div className="mt-5 border-t border-[#dce6e0] pt-5">
          <h3 className="mb-4 font-semibold">Write a review</h3><label className="block text-sm">Review note<textarea aria-label="Review note" className="my-2 block min-h-32 w-full rounded-lg border border-[#ccdcd4] p-3" maxLength={2000} disabled={busy || confirm} value={note} onChange={e => setNote(e.target.value)} placeholder="Fictional observations for demonstration." /></label>
          <label className="block text-sm">Follow-up<textarea aria-label="Follow-up" className="my-2 block min-h-20 w-full rounded-lg border border-[#ccdcd4] p-3" maxLength={1000} disabled={busy || confirm} value={followUp} onChange={e => setFollowUp(e.target.value)} placeholder="Fictional next step for demonstration." /></label>
          {confirm ? <div className="mt-4 rounded-xl bg-[#f4f7f6] p-4"><p className="mb-4 text-sm">Publish this note and follow-up to {detail.patient_name}? The patient can read it immediately. Published reviews are fixed in this demo.</p><button className="btn" disabled={busy} onClick={publish}>{busy ? "Publishing…" : "Confirm publish"}</button><button className="btn secondary ml-3" disabled={busy} onClick={() => setConfirm(false)}>Keep editing</button></div> : <button className="btn mt-4" disabled={busy || !note.trim() || !followUp.trim()} onClick={() => setConfirm(true)}>Publish review</button>}
          <p className="muted mt-4 text-xs">Unpublished text stays only in this screen and clears when you change doctor or assessment. Reviews do not issue prescriptions or change appointment status.</p>
        </div>}
      </> : <><h2 className="font-semibold">Choose a shared assessment</h2><p className="muted mt-3">Open an inbox entry to view the patient's photo, message and published review.</p></>}</section>
    </div>
  </>;
}
