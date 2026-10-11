"use client";
import { useEffect, useMemo, useState } from "react";
import { Consultation, DemoApi, DemoDoctor, doctorNames, queueToken, visitTime } from "@smart-skin/shared";
const base=process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000";
export default function ConsultationPage(){
  const [doctor,setDoctor]=useState<DemoDoctor>("doctor-lim");
  return <main className="mx-auto max-w-6xl px-5 py-7 md:px-10"><header className="mb-7 flex flex-wrap items-center justify-between gap-4"><div><strong className="text-xl">Smart Skin</strong><p className="muted text-sm">Visit consultations</p></div><nav className="flex gap-3"><a className="btn secondary" href="/">Patient queue</a><a className="btn secondary" href="/care">Prescriptions & billing</a></nav></header>
    <div className="mb-6 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Demo identities only. Use fictional findings and follow-up. Linked AI output remains simulated.</div>
    <h1 className="text-3xl font-semibold">Consultation notes</h1><p className="muted my-3">Open an assigned called visit, check its authorized assessment and publish a note for the patient.</p>
    <label className="panel my-6 block max-w-md text-sm font-semibold">Doctor demo identity<select className="mt-2" value={doctor} onChange={e=>setDoctor(e.target.value as DemoDoctor)}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id=><option key={id} value={id}>{doctorNames[id]}</option>)}</select></label>
    <Workspace key={doctor} doctor={doctor}/></main>;
}
function Workspace({doctor}:{doctor:DemoDoctor}){
  const api=useMemo(()=>new DemoApi(base,doctor),[doctor]);
  const [records,setRecords]=useState<Consultation[]>([]),[detail,setDetail]=useState<Consultation|null>(null),[selected,setSelected]=useState("");
  const [findings,setFindings]=useState(""),[followUp,setFollowUp]=useState("");
  const [busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  useEffect(()=>{
    let active=true,fetching=false;
    async function load(){
      if(fetching)return;fetching=true;
      try{const data=await api.consultations();const opened=selected&&data.some(r=>r.visit.id===selected)?await api.consultation(selected):null;
        if(active){setRecords(data);setDetail(opened);if(selected&&!opened){setSelected("");setConfirm(false);setNotice("This visit is no longer available.");}}
      }catch(e){if(active){setDetail(null);setError(e instanceof Error?e.message:"Cannot load consultations.");}}
      finally{fetching=false;}
    }
    void load();const timer=setInterval(load,3000);return()=>{active=false;clearInterval(timer);};
  },[api,selected]);
  async function open(id:string){
    if(busy)return;setBusy(true);setError("");setNotice("");setConfirm(false);setDetail(null);
    try{setDetail(await api.consultation(id));setSelected(id);setFindings("");setFollowUp("");}
    catch(e){setSelected("");setError(e instanceof Error?e.message:"Visit unavailable.");}finally{setBusy(false);}
  }
  async function publish(){
    if(!detail||busy)return;setBusy(true);setError("");
    try{const saved=await api.publishConsultation(detail.visit.id,findings.trim(),followUp.trim());setDetail(current=>current?{...current,note:saved.note}:null);setConfirm(false);setNotice("Consultation note published. The patient can read it under My visits.");}
    catch(e){setError(e instanceof Error?e.message:"Cannot publish. Refresh before retrying.");}finally{setBusy(false);}
  }
  return <>{error?<div role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</div>:null}{notice?<p role="status" className="mb-5 rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</p>:null}
    <div className="grid items-start gap-6 lg:grid-cols-[320px_1fr]"><section className="panel"><h2 className="mb-4 font-semibold">Assigned visits</h2>{records.map(r=><button key={r.visit.id} aria-label={`Open consultation ${queueToken(r.visit)}`} disabled={busy} className="mb-3 block w-full rounded-xl border border-[#dce6e0] p-4 text-left" onClick={()=>open(r.visit.id)}><strong>{queueToken(r.visit)} · {r.visit.patient_name}</strong><span className="muted my-2 block text-xs">{visitTime(r.visit.starts_at)} · {r.visit.status}</span><span className="badge">{r.note?"Published":r.visit.status==="called"?"Ready for note":"No published note"}</span></button>)}{!records.length?<p className="muted">No called or completed visits for this doctor.</p>:null}</section>
    <section className="panel">{detail?<><h2 className="text-xl font-semibold">{queueToken(detail.visit)} · {detail.visit.patient_name}</h2><p className="muted mt-2 text-sm">{detail.visit.doctor_name} · {visitTime(detail.visit.starts_at)} · {detail.visit.status}</p>
      <h3 className="mt-5 font-semibold">Linked assessment</h3>{detail.linked_share?<><p className="muted my-3 whitespace-pre-wrap">{detail.linked_share.patient_message||"No patient message provided."}</p>{detail.linked_share.assessment?.photo_uri?<img alt="Appointment-linked assessment photo" src={detail.linked_share.assessment.photo_uri} className="my-4 max-h-72 w-full rounded-xl bg-[#f4f7f6] object-contain"/>:null}<p className="my-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">SIMULATION · {detail.linked_share.assessment?.example_category}. {detail.linked_share.assessment?.message}</p></>:<p className="muted my-3">No active assessment link for this visit. The patient can choose what to share.</p>}
      {detail.note?<div className="mt-5 border-t border-[#dce6e0] pt-5"><h3 className="font-semibold">Published doctor findings</h3><p className="muted my-3 whitespace-pre-wrap">{detail.note.findings}</p><h3 className="font-semibold">Follow-up</h3><p className="muted my-3 whitespace-pre-wrap">{detail.note.follow_up}</p><p className="muted text-xs">Published {visitTime(detail.note.created_at)} · saved note cannot be replaced.</p></div>:detail.visit.status==="called"?<div className="mt-5 border-t border-[#dce6e0] pt-5"><label className="block text-sm">Doctor findings<textarea aria-label="Doctor findings" maxLength={2000} disabled={busy||confirm} value={findings} onChange={e=>setFindings(e.target.value)} className="my-2 block min-h-32 w-full rounded-lg border border-[#ccdcd4] p-3" placeholder="Fictional findings for this demonstration."/></label><label className="block text-sm">Follow-up<textarea aria-label="Consultation follow-up" maxLength={1000} disabled={busy||confirm} value={followUp} onChange={e=>setFollowUp(e.target.value)} className="my-2 block min-h-20 w-full rounded-lg border border-[#ccdcd4] p-3"/></label>
        {confirm?<div className="mt-4 rounded-xl bg-[#f4f7f6] p-4"><p className="mb-4 text-sm">Publish these findings and follow-up for {queueToken(detail.visit)}? The patient can read them immediately. Published notes cannot be replaced in this increment.</p><button className="btn" disabled={busy} onClick={publish}>Confirm consultation publication</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setConfirm(false)}>Keep editing</button></div>:<button className="btn mt-4" disabled={busy||!findings.trim()||!followUp.trim()} onClick={()=>setConfirm(true)}>Publish consultation note</button>}<p className="muted mt-3 text-xs">Unsaved text clears when changing doctor or visit. Publication does not complete the queue visit or issue a prescription.</p>
      </div>:<p className="muted mt-5">This visit is completed. New notes can only be published while a visit is called.</p>}
    </>:<p className="muted">Choose an assigned visit to open its consultation.</p>}</section></div></>;
}
