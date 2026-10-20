"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Booking, DemoApi, queueToken, visitTime } from "@smart-skin/shared";
import CounterBooking from "./CounterBooking";
import RescheduleVisit from "./RescheduleVisit";
import MissedVisitReview from "./MissedVisitReview";
const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export default function QueuePage() {
  const api = useMemo(() => new DemoApi(base, "staff-demo"), []);
  const [doctor, setDoctor] = useState("doctor-lim");
  const [date, setDate] = useState("");
  const [records, setRecords] = useState<Booking[]>([]);
  const [busy, setBusy] = useState(false);
  const [attendance,setAttendance]=useState<{visit:Booking;mode:"mark"|"restore"}|null>(null);
  const [moving,setMoving]=useState<Booking|null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [synced, setSynced] = useState("");
  useEffect(() => { let active = true; api.slots().then(data => { if(active) { setDate(data[0]?.clinic_date || ""); } }).catch(e => { if(active) setError(e.message); }); return () => { active=false; }; }, [api]);
  const refresh = useCallback(async () => {
    if (!date) return;
    const data = await api.queue(doctor, date);
    setRecords(data); setSynced(new Date().toLocaleTimeString()); setError("");
  }, [api, doctor, date]);
  useEffect(() => {
    let active = true;
    let loading = false;
    const poll = async () => { if(loading || !date) return; loading=true; try { const data=await api.queue(doctor,date); if(active) { setRecords(data); setSynced(new Date().toLocaleTimeString()); setError(""); } } catch(e) { if(active) setError(e instanceof Error ? e.message : "Refresh failed."); } finally { loading=false; } };
    setRecords([]); setAttendance(null); void poll(); const timer=setInterval(poll,3000);
    return () => { active=false; clearInterval(timer); };
  }, [api,doctor,date]);
  async function action(fn: () => Promise<Booking>, message: string) {
    if (busy) return; setBusy(true); setError(""); setNotice("");
    try { await fn(); setAttendance(null); await refresh(); setNotice(message); } catch(e) { setError(e instanceof Error ? e.message : "Action failed."); } finally { setBusy(false); }
  }
  const attendanceChanged=!!attendance&&!records.some(record=>record.id===attendance.visit.id&&record.status===(attendance.mode==="restore"?"missed":"waiting")&&(attendance.mode!=="restore"||record.missed_event_id===attendance.visit.missed_event_id));
  const called = records.find(r => r.status === "called");
  const waiting = records.filter(r => r.status === "waiting");
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10">
    <header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="rounded-xl bg-[#176f5e] px-3 py-2 text-xl font-bold text-white">S+</span><div><strong className="text-lg">Smart Skin</strong><p className="muted text-xs">Care coordination dashboard</p></div></div><span className="badge">Staff Demo · synthetic data</span></header>
    <div className="mb-7 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">Local demonstration — demo identities are not secure login. Use synthetic records only. Queue actions apply to the selected clinic date.</div>
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="muted mb-2 text-xs font-semibold tracking-widest">REGISTRATION / VISIT QUEUE</p><h1 className="text-3xl font-semibold">Keep every visit moving.</h1><p className="muted mt-2">Bookings from the patient app appear here automatically.</p></div><button className="btn secondary" disabled={!date || busy} onClick={() => refresh().catch(e => setError(e.message))}>Refresh queue</button></div>
    <CounterBooking api={api} onBooked={booking=>{setDoctor(booking.doctor_id);setDate(booking.clinic_date);}}/>
    {moving?<RescheduleVisit key={moving.id} api={api} booking={moving} onClose={()=>setMoving(null)} onSaved={saved=>{setMoving(null);setDoctor(saved.doctor_id);setDate(saved.clinic_date);setNotice(`Visit rescheduled: ${queueToken(saved)} · ${saved.patient_name} · ${visitTime(saved.starts_at)}.`);if(saved.doctor_id===doctor&&saved.clinic_date===date)void refresh().catch(e=>setError(e.message));}}/>:null}
    {attendance?<MissedVisitReview visit={attendance.visit} mode={attendance.mode} busy={busy} changed={attendanceChanged} onCancel={()=>{setAttendance(null);setError("");}} onConfirm={()=>{if(attendanceChanged)return;const {visit,mode}=attendance;void action(()=>mode==="restore"?api.restoreWaiting(visit.id,visit.missed_event_id!):api.markMissed(visit.id),mode==="restore"?"Visit restored to waiting with its original queue number.":"Appointment marked missed. The patient can book another visit.");}}/>:null}
    <section className="panel mb-6 grid gap-5 md:grid-cols-3"><label className="text-sm font-semibold">Doctor<select className="mt-2" disabled={busy} value={doctor} onChange={e=>setDoctor(e.target.value)}><option value="doctor-lim">Dr. Lim (demo)</option><option value="doctor-anita">Dr. Anita (demo)</option></select></label><label className="text-sm font-semibold">Clinic date<input type="date" className="mt-2 block w-full rounded-lg border border-[#ccdcd4] bg-white p-3" disabled={busy} value={date} onChange={e=>setDate(e.target.value)}/><span className="muted mt-2 block text-xs font-normal">Malaysia date. Past dates are available for attendance review.</span></label><div className="flex flex-col justify-center text-sm"><span className="muted">Shared local API</span><span className="mt-2">{synced ? `Last checked ${synced}` : "Connecting…"}</span></div></section>
    {error && <div role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}<button className="ml-4 underline" onClick={()=>api.slots().then(data=>{if(!date)setDate(data[0]?.clinic_date || ""); return refresh();}).catch(e=>setError(e.message))}>Retry connection</button></div>}
    {notice && <p role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</p>}
    <section className="mb-6 grid gap-5 md:grid-cols-3"><div className="panel"><p className="muted text-sm">Waiting patients</p><p className="mt-3 text-4xl font-semibold">{waiting.length}</p><p className="muted mt-3 text-xs">Ordered by appointment time, then queue number</p></div><div className="panel"><p className="muted text-sm">Now serving</p><p className="mt-3 text-4xl font-semibold">{called ? queueToken(called) : "—"}</p><p className="muted mt-3 text-xs">{called?.patient_name || "No patient called yet"}</p></div><div className="panel flex flex-col justify-between gap-4"><p className="text-sm">Call one patient at a time. Complete the current visit before continuing.</p><button className="btn" disabled={busy || !!called || waiting.length===0} onClick={()=>action(()=>api.callNext(doctor,date),"Next patient called. Their app will show the update.")}>{busy ? "Saving…" : "Call next patient"}</button></div></section>
    <section className="panel"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Visit list</h2><span className="muted text-sm">{records.length} records</span></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Queue</th><th>Patient</th><th>Appointment</th><th>Status</th><th>Action</th></tr></thead><tbody>{records.map(r=><tr key={r.id}><td className="font-bold">{queueToken(r)}</td><td>{r.patient_name}</td><td>{visitTime(r.starts_at)}</td><td><span className={`badge ${r.status}`}>{r.rescheduled_to_id?"Rescheduled":r.status.charAt(0).toUpperCase()+r.status.slice(1)}</span></td><td>{r.status==="called" ? <button className="btn secondary" disabled={busy} onClick={()=>action(()=>api.complete(r.id),"Visit marked completed.")}>Complete visit</button> : r.status==="waiting"&&new Date(r.starts_at).getTime()>Date.now()?<button className="btn secondary" disabled={busy||!!moving} onClick={()=>{setMoving(r);setNotice("");}}>Reschedule {queueToken(r)}</button>: r.status==="missed"&&r.missed_event_id?<button className="btn secondary" disabled={busy||!!moving||!!attendance} onClick={()=>{setAttendance({visit:r,mode:"restore"});setNotice("");setError("");}}>Restore to waiting {queueToken(r)}</button>: r.status==="waiting"&&r.ends_at&&new Date(r.ends_at).getTime()<=Date.now()?<button className="btn secondary" disabled={busy||!!moving||!!attendance} onClick={()=>{setAttendance({visit:r,mode:"mark"});setNotice("");setError("");}}>Mark missed {queueToken(r)}</button>: <span className="muted">—</span>}</td></tr>)}</tbody></table></div>{records.length===0 && <div className="py-12 text-center"><h3 className="font-semibold">No bookings for this clinic session</h3><p className="muted mt-2 text-sm">Book a visit from the patient app, or select another doctor/date.</p></div>}</section>
    <footer className="muted mt-6 flex flex-wrap gap-6 text-sm"><a className="font-semibold underline" href="/schedules">Doctor schedules →</a><a className="font-semibold underline" href="/slots">Appointment slots →</a><a className="font-semibold underline" href="/doctors">Doctor profiles →</a><a className="font-semibold underline" href="/care">Open prescriptions & billing →</a><a className="font-semibold underline" href="/reviews">Doctor assessment reviews →</a><a className="font-semibold underline" href="/consultations">Consultation notes →</a><a className="font-semibold underline" href="/feedback">Visit feedback →</a><a className="font-semibold underline" href="/reports">Daily reports →</a></footer>
  </main>;
}
