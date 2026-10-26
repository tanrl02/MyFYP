"use client";
import {useEffect,useRef,useState} from "react";
import {DemoApi,UserProfile} from "@smart-skin/shared";

export default function AddPatient({api,busy,onBusy,onSaved,onClose}:{api:DemoApi;busy:boolean;onBusy:(busy:boolean)=>void;onSaved:(user:UserProfile)=>void;onClose:()=>void}){
  const [draft,setDraft]=useState({name:"",phone:"",email:""});
  const [request]=useState(()=>`patient-${crypto.randomUUID()}`);
  const [review,setReview]=useState(false),[attempted,setAttempted]=useState(false),[error,setError]=useState("");
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus();},[review]);
  function prepare(){const name=draft.name.trim(),phone=draft.phone.trim(),email=draft.email.trim();
    if(!name||/[\x00-\x1f\x7f]/.test(name)){setError("Enter a patient name on one line.");return;}
    if(phone&&(!/^\+?[0-9 ()-]+$/.test(phone)||phone.replace(/\D/g,"").length<7||phone.replace(/\D/g,"").length>15)){setError("Enter a phone number with 7–15 digits, or leave it blank.");return;}
    if(email&&!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){setError("Enter a valid email address, or leave it blank.");return;}
    setDraft({name,phone,email});setError("");setReview(true);}
  async function save(){if(!review||busy)return;setAttempted(true);onBusy(true);setError("");
    try{onSaved(await api.createPatient({...draft,request_id:request}));}
    catch(e){setError(e instanceof Error?e.message:"Cannot add patient. Retry this confirmation to check the same request.");}
    finally{onBusy(false);}}
  return <section aria-label="Add patient" className="panel my-5"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{review?"Review new patient":"Add patient"}</h2>
    <p className="muted my-3">Creates a patient profile with a unique ID and separate records. Use fictional information. Registration and login are not enabled.</p>
    {error?<p role="alert" className="my-3 text-red-800">{error}{attempted?" Retry confirmation with these same details to avoid a duplicate. Check the directory before starting another form.":""}</p>:null}
    {review?<><dl>{([{key:"name",label:"Name"},{key:"phone",label:"Phone"},{key:"email",label:"Email"}] as const).map(field=><div className="my-3 break-words" key={field.key}><dt className="font-semibold">{field.label}</dt><dd>{draft[field.key]||"Not provided"}</dd></div>)}</dl><p className="my-3">Role: Patient. Existing users and their records stay unchanged.</p><button className="btn" disabled={busy} onClick={save}>{busy?"Saving…":"Confirm add patient"}</button><button className="btn secondary ml-3" disabled={busy||attempted} onClick={()=>{setReview(false);setError("");}}>Keep editing patient</button></>:<fieldset disabled={busy}>{([{key:"name",label:"Patient name",max:100},{key:"phone",label:"Patient phone",max:30},{key:"email",label:"Patient email",max:254}] as const).map(field=><label key={field.key} className="my-3 block font-semibold">{field.label}<input aria-label={field.label} maxLength={field.max} type={field.key==="email"?"email":field.key==="phone"?"tel":"text"} value={draft[field.key]} onChange={event=>{setError("");setDraft({...draft,[field.key]:event.target.value});}} className="mt-2 block w-full rounded-lg border p-3 font-normal"/></label>)}<button className="btn" onClick={prepare}>Review new patient</button></fieldset>}
    <button className="btn secondary mt-4" disabled={busy} onClick={onClose}>Close patient form</button>
  </section>;
}
