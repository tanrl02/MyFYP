import { useEffect, useState } from "react";
import { Booking, Consultation, ConsultationDraft, DemoApi, queueToken, visitTime } from "@smart-skin/shared";

export default function ConsultationEditor({api,visit,busy,onBusy,onPublished}:{api:DemoApi;visit:Booking;busy:boolean;onBusy:(value:boolean)=>void;onPublished:(record:Consultation)=>void}){
  const [draft,setDraft]=useState<ConsultationDraft|null>(null);
  const [findings,setFindings]=useState(""),[followUp,setFollowUp]=useState("");
  const [loading,setLoading]=useState(true),[reload,setReload]=useState(0),[confirm,setConfirm]=useState(false);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  const editable=visit.status==="called";
  useEffect(()=>{
    let active=true;
    setLoading(true);setConfirm(false);setError("");setDraft(null);
    api.consultationDraft(visit.id).then(saved=>{
      if(active){setDraft(saved);setFindings(saved.findings);setFollowUp(saved.follow_up);}
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"Cannot load the private draft.");})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[api,visit.id,reload]);
  const dirty=!!draft&&(findings.trim()!==draft.findings||followUp.trim()!==draft.follow_up);
  async function save(){
    if(!draft||busy||loading||!editable)return;
    onBusy(true);setError("");setNotice("");
    try{const saved=await api.saveConsultationDraft(visit.id,findings.trim(),followUp.trim(),draft.version);setDraft(saved);setFindings(saved.findings);setFollowUp(saved.follow_up);setNotice("Private draft saved. The patient cannot see it.");}
    catch(e){setError(e instanceof Error?e.message:"Cannot save draft. Your text is still here.");}
    finally{onBusy(false);}
  }
  async function publish(){
    if(!draft||busy||loading||!editable)return;
    onBusy(true);setError("");setNotice("");
    try{onPublished(await api.publishConsultation(visit.id,findings.trim(),followUp.trim(),draft.version));}
    catch(e){setConfirm(false);setError(e instanceof Error?e.message:"Cannot publish. Your text is still here.");}
    finally{onBusy(false);}
  }
  return <section className="mt-5 border-t border-[#dce6e0] pt-5" aria-label="Private consultation draft">
    <h3 className="font-semibold">Private consultation draft</h3>
    <p className="muted my-3 text-sm">Only the assigned doctor can read this draft. Save before leaving; only published notes are visible to the patient.</p>
    {!editable?<p className="my-3 rounded-lg bg-amber-50 p-3 text-sm">This visit is completed. Saved drafts remain private and read-only. New notes can only be published while a visit is called.</p>:null}
    {error?<p role="alert" className="my-3 rounded-lg bg-red-50 p-3 text-red-800">{error}</p>:null}
    {notice?<p role="status" className="my-3 rounded-lg bg-emerald-50 p-3 text-emerald-800">{notice}</p>:null}
    {loading?<p role="status" className="muted my-3">Loading saved draft…</p>:null}
    {draft?<>
      <p className="muted my-3 text-sm">{draft.updated_at?`Draft saved ${visitTime(draft.updated_at)}`:"No saved draft yet."}{dirty?" · Unsaved changes":""}</p>
      <label className="block text-sm">Doctor findings<textarea aria-label="Doctor findings" maxLength={2000} disabled={busy||confirm||loading||!editable} value={findings} onChange={e=>setFindings(e.target.value)} className="my-2 block min-h-32 w-full rounded-lg border border-[#ccdcd4] p-3" placeholder="Fictional findings for this demonstration."/></label>
      <label className="block text-sm">Follow-up<textarea aria-label="Consultation follow-up" maxLength={1000} disabled={busy||confirm||loading||!editable} value={followUp} onChange={e=>setFollowUp(e.target.value)} className="my-2 block min-h-20 w-full rounded-lg border border-[#ccdcd4] p-3"/></label>
    </>:null}
    {!confirm?<div className="my-4 flex flex-wrap gap-3">
      {editable?<button className="btn secondary" disabled={busy||loading||!dirty} onClick={save}>Save draft</button>:null}
      <button className="underline" disabled={busy||loading} onClick={()=>{setNotice("Reloading replaces any unsaved text with the saved draft.");setReload(value=>value+1);}}>Reload saved draft</button>
      {editable?<button className="btn" disabled={busy||loading||!draft||!findings.trim()||!followUp.trim()} onClick={()=>{setError("");setConfirm(true);}}>Publish consultation note</button>:null}
    </div>:<div className="mt-4 rounded-xl bg-[#f4f7f6] p-4">
      <p className="mb-4 text-sm">Publish these findings and follow-up for {queueToken(visit)}? The patient can read them immediately. Published notes cannot be replaced.</p>
      <dl className="mb-4 space-y-3 whitespace-pre-wrap break-words"><div><dt className="font-semibold">Doctor findings</dt><dd>{findings.trim()}</dd></div><div><dt className="font-semibold">Follow-up</dt><dd>{followUp.trim()}</dd></div></dl>
      <button className="btn" disabled={busy} onClick={publish}>Confirm consultation publication</button><button className="btn secondary ml-3" disabled={busy} onClick={()=>setConfirm(false)}>Keep editing</button>
    </div>}
    <p className="muted mt-3 text-xs">Only saved drafts survive reloads or changing doctor/visit. Reload saved draft discards unsaved changes. Publication does not complete the queue visit or issue a prescription.</p>
  </section>;
}
