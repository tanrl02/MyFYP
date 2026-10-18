"use client";
import AssessmentResult from "../components/AssessmentResult";
import { useEffect, useMemo, useState } from "react";
import { Consultation, DemoApi, DemoDoctor, doctorNames, queueToken, visitTime } from "@smart-skin/shared";
import ConsultationHistory from "./ConsultationHistory";
import FollowUpRecommendation from "./FollowUpRecommendation";
import ConsultationEditor from "./ConsultationEditor";
const base=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000";
export default function ConsultationPage(){
  const [doctor,setDoctor]=useState<DemoDoctor>("doctor-lim");
  const [busy,setBusy]=useState(false);
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10"><header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Visit consultations</p></div><nav className="flex gap-3"><a className="btn secondary" href="/">Patient queue</a><a className="btn secondary" href="/care">Prescriptions & billing</a></nav></header>
    <div className="mb-6 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Demo identities only. Use fictional findings and follow-up. New AI suggestions are experimental; older records remain simulations. Review the photo independently.</div>
    <h1 className="text-3xl font-semibold">Consultation notes</h1><p className="muted my-3">Open an assigned called visit, check its authorized assessment and publish a note for the patient.</p>
    <label className="panel my-6 block max-w-md text-sm font-semibold">Doctor demo identity<select className="mt-2" value={doctor} disabled={busy} onChange={e=>setDoctor(e.target.value as DemoDoctor)}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id=><option key={id} value={id}>{doctorNames[id]}</option>)}</select></label>
    <Workspace key={doctor} doctor={doctor} busy={busy} onBusy={setBusy}/></main>;
}
function Workspace({doctor,busy,onBusy}:{doctor:DemoDoctor;busy:boolean;onBusy:(value:boolean)=>void}){
  const api=useMemo(()=>new DemoApi(base,doctor),[doctor]);
  const [records,setRecords]=useState<Consultation[]>([]),[detail,setDetail]=useState<Consultation|null>(null),[selected,setSelected]=useState("");
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  useEffect(()=>{
    if(busy)return;
    let active=true,fetching=false;
    async function load(){
      if(fetching)return;fetching=true;
      try{const data=await api.consultations();const opened=selected&&data.some(r=>r.visit.id===selected)?await api.consultation(selected):null;
        if(active){setRecords(data);setDetail(opened);if(selected&&!opened){setSelected("");setNotice("This visit is no longer available.");}}
      }catch(e){if(active){setDetail(null);setError(e instanceof Error?e.message:"Cannot load consultations.");}}
      finally{fetching=false;}
    }
    void load();const timer=setInterval(load,3000);return()=>{active=false;clearInterval(timer);};
  },[api,selected,busy]);
  async function open(id:string){
    if(busy)return;onBusy(true);setError("");setNotice("");setDetail(null);
    try{setDetail(await api.consultation(id));setSelected(id);}
    catch(e){setSelected("");setError(e instanceof Error?e.message:"Visit unavailable.");}finally{onBusy(false);}
  }
  return <>{error?<div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div>:null}{notice?<p role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</p>:null}
    <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]"><section className="panel"><h2 className="mb-4 font-semibold">Assigned visits</h2>{records.map(r=><button key={r.visit.id} aria-label={`Open consultation ${queueToken(r.visit)} · ${visitTime(r.visit.starts_at)}`} disabled={busy} className="mb-3 block w-full rounded-xl border border-[#dce6e0] p-4 text-left" onClick={()=>open(r.visit.id)}><strong>{queueToken(r.visit)} · {r.visit.patient_name}</strong><span className="muted my-2 block text-xs">{visitTime(r.visit.starts_at)} · {r.visit.status}</span><span className="badge">{r.note?"Published":r.visit.status==="called"?"Ready for note":"No published note"}</span></button>)}{!records.length?<p className="muted">No called or completed visits for this doctor.</p>:null}</section>
    <section className="panel">{detail?<><h2 className="text-xl font-semibold">{queueToken(detail.visit)} · {detail.visit.patient_name}</h2><p className="muted mt-2 text-sm">{detail.visit.doctor_name} · {visitTime(detail.visit.starts_at)} · {detail.visit.status}</p>
      <section className="mt-5 rounded-xl bg-[#f4f7f6] p-4" aria-label="Patient background"><h3 className="font-semibold">Patient background</h3><p className="muted my-2 text-xs">Latest patient-provided information, not a historical snapshot of this visit. Blank fields mean not provided.</p>{detail.background?<><dl className="space-y-3">{([["allergies","Allergies"],["medicines","Current medicines"],["conditions","Existing conditions"]] as const).map(([key,label])=><div key={key}><dt className="text-sm font-semibold">{label}</dt><dd className="muted whitespace-pre-wrap break-words text-sm">{detail.background?.[key]||"Not provided"}</dd></div>)}</dl><p className="muted mt-3 text-xs">{detail.background.updated_at?`Last saved ${visitTime(detail.background.updated_at)}`:"No medical background saved yet."}</p></>:<p className="muted">Background unavailable. Reopen this visit to retry.</p>}</section>
      <FollowUpRecommendation key={`follow-up-${detail.visit.id}`} api={api} visit={detail.visit} recommendation={detail.follow_up||null}/>
      <ConsultationHistory key={`history-${detail.visit.id}`} api={api} bookingId={detail.visit.id}/>
      <h3 className="mt-5 font-semibold">Linked assessment</h3>{detail.linked_share?<><p className="muted my-3 whitespace-pre-wrap">{detail.linked_share.patient_message||"No patient message provided."}</p>{detail.linked_share.assessment?.photo_uri?<img alt="Appointment-linked assessment photo" src={detail.linked_share.assessment.photo_uri} className="my-4 max-h-72 w-full rounded-xl bg-[#f4f7f6] object-contain"/>:null}{detail.linked_share.assessment?<AssessmentResult assessment={detail.linked_share.assessment}/>:null}</>:<p className="muted my-3">No active assessment link for this visit. The patient can choose what to share.</p>}
      {detail.note?<div className="mt-5 border-t border-[#dce6e0] pt-5"><h3 className="font-semibold">Published doctor findings</h3><p className="muted my-3 whitespace-pre-wrap">{detail.note.findings}</p><h3 className="font-semibold">Follow-up</h3><p className="muted my-3 whitespace-pre-wrap">{detail.note.follow_up}</p><p className="muted text-xs">Published {visitTime(detail.note.created_at)} · saved note cannot be replaced.</p></div>:<ConsultationEditor key={detail.visit.id} api={api} visit={detail.visit} busy={busy} onBusy={onBusy} onPublished={saved=>{setDetail(current=>current?.visit.id===saved.visit.id?{...current,note:saved.note}:current);setNotice("Consultation note published. The patient can read it under My visits.");}}/>}
    </>:<p className="muted">Choose an assigned visit to open its consultation.</p>}</section></div></>;
}
