"use client";
import {useStaffIdentity} from "../StaffIdentity";
import useDoctorNames from "../useDoctorNames";
import {useEffect,useMemo,useRef,useState} from "react";
import {DemoActor,DemoApi,StaffStatus,UserProfile,visitTime} from "@smart-skin/shared";
import AddUser from "./AddUser";

const initialIdentities:Partial<Record<DemoActor,string>>={"admin-demo":"Admin Demo","staff-demo":"Staff Demo","doctor-lim":"Dr. Lim (demo)","doctor-anita":"Dr. Anita (demo)","patient-ava":"Ava Demo","patient-noah":"Noah Demo"};
const roles={all:"All roles",patient:"Patient",doctor:"Doctor",staff:"Staff",admin:"Admin"} as const;
const fields=[{key:"name",label:"Name",max:100},{key:"phone",label:"Phone",max:30},{key:"email",label:"Email",max:254}] as const;
type Draft={original:UserProfile;name:string;phone:string;email:string;review:boolean};
export default function UsersPage(){
  const {names:staffNames}=useStaffIdentity();
  const doctorNames=useDoctorNames();
  const [statuses,setStatuses]=useState<StaffStatus[]>([]),[statusReview,setStatusReview]=useState<{original:StaffStatus;name:string;request:string}|null>(null);
  const [creating,setCreating]=useState<"patient"|"doctor"|"staff"|null>(null);
  const identities={...initialIdentities,...doctorNames,...staffNames};
  const [actor,setActor]=useState<DemoActor>("admin-demo");
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000",actor),[actor]);
  useEffect(()=>{if(actor.startsWith("staff-")&&!staffNames[actor as `staff-${string}`])setActor("staff-demo");},[actor,staffNames]);
  const admin=actor==="admin-demo";
  const [users,setUsers]=useState<UserProfile[]>([]),[own,setOwn]=useState<{actor:DemoActor;profile:UserProfile}|null>(null);
  const [query,setQuery]=useState(""),[role,setRole]=useState<keyof typeof roles>("all");
  const [draft,setDraft]=useState<Draft|null>(null),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [error,setError]=useState(""),[notice,setNotice]=useState(""),[retry,setRetry]=useState(0);
  const epoch=useRef(0),saving=useRef(false),heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{
    let active=true,fetching=false;setUsers([]);setStatuses([]);setStatusReview(null);setOwn(null);setDraft(null);setCreating(null);setQuery("");setRole("all");setError("");setNotice("");setLoading(true);
    async function load(){if(fetching||saving.current)return;fetching=true;const revision=epoch.current;
      try{const [profile,list,statusList]=await Promise.all([api.me(),actor==="admin-demo"?api.users():Promise.resolve([]),actor==="admin-demo"?api.staffStatuses():Promise.resolve([])]);if(active&&revision===epoch.current){setOwn({actor,profile});setUsers(list);setStatuses(statusList);setError("");}}
      catch(e){if(active&&revision===epoch.current)setError(e instanceof Error?e.message:"Cannot load user information.");}
      finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};
  },[api,actor,retry]);
  useEffect(()=>{if(draft?.review)heading.current?.focus();},[draft?.review]);
  const search=query.trim().toLowerCase();
  const visible=users.filter(user=>(role==="all"||user.role===role)&&(!search||[user.id,user.name,user.phone,user.email].some(value=>value.toLowerCase().includes(search))));
  const current=users.find(user=>user.id===draft?.original.id);
  const changed=!!draft&&(!current||current.version!==draft.original.version);
  function review(){if(!draft||busy||changed)return;
    const name=draft.name.trim(),phone=draft.phone.trim(),email=draft.email.trim();
    if(!name||/[\x00-\x1f\x7f]/.test(name)){setError("Enter a name on one line.");return;}
    if(phone&&(!/^\+?[0-9 ()-]+$/.test(phone)||phone.replace(/\D/g,"").length<7||phone.replace(/\D/g,"").length>15)){setError("Enter a phone number with 7–15 digits, or leave it blank.");return;}
    if(email&&!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){setError("Enter a valid email address, or leave it blank.");return;}
    if(fields.every(field=>({name,phone,email})[field.key]===draft.original[field.key])){setError("Change at least one field before reviewing.");return;}
    setError("");setDraft({...draft,name,phone,email,review:true});}
  async function save(){if(!draft?.review||busy||changed||!admin)return;
    saving.current=true;epoch.current++;setBusy(true);setError("");setNotice("");
    try{const saved=await api.saveUser(draft.original.id,{name:draft.name,phone:draft.phone,email:draft.email,version:draft.original.version});epoch.current++;
      setUsers(rows=>rows.map(user=>user.id===saved.id?saved:user));if(saved.id===actor)setOwn({actor,profile:saved});setDraft(null);setNotice(`User information saved for ${saved.name}.`);}
    catch(e){setError(e instanceof Error?e.message:"Cannot save user information. Reload before retrying.");}
    finally{saving.current=false;setBusy(false);}}
  const reviewedStatus=statuses.find(row=>row.staff_id===statusReview?.original.staff_id);
  const statusChanged=!!statusReview&&(!reviewedStatus||reviewedStatus.version!==statusReview.original.version);
  useEffect(()=>{if(statusReview)heading.current?.focus();},[statusReview]);
  async function saveStatus(){if(!statusReview||busy||saving.current||statusChanged||!admin)return;
    saving.current=true;epoch.current++;setBusy(true);setError("");setNotice("");
    try{const saved=await api.saveStaffStatus(statusReview.original.staff_id,{active:!statusReview.original.active,version:statusReview.original.version,request_id:statusReview.request});epoch.current++;
      setStatuses(rows=>rows.map(row=>row.staff_id===saved.staff_id?saved:row));setNotice(`${statusReview.name}: ${saved.active?"Active":"Inactive"}. Previous records are retained.`);setStatusReview(null);}
    catch(e){setError(e instanceof Error?e.message:"Cannot change staff status. Refresh and review again.");}
    finally{saving.current=false;setBusy(false);}}
  const profile=own?.actor===actor?own.profile:null;
  return <main className="mx-auto max-w-6xl p-6 md:p-10">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4"><div><p className="eyebrow">Smart Skin</p><h1 className="text-3xl font-semibold">User management</h1></div><nav className="flex gap-5 text-sm"><a className="underline" href="/doctors">Doctor specialty & expertise</a><a className="underline" href="/">Patient queue</a></nav></header>
    <p className="muted my-4">Synthetic demonstration only. Demo identity selection is not secure login. Use fictional contact details. Admin manages basic user information; clinical records are excluded.</p>
    <label className="mb-5 block font-semibold">Demo identity<select aria-label="Demo identity" className="ml-3 rounded-lg border p-2" value={actor} disabled={busy} onChange={event=>setActor(event.target.value as DemoActor)}>{Object.entries(identities).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
    {loading?<p role="status">Loading user information…</p>:null}
    {error?<p role="alert" className="my-4 rounded-lg bg-red-50 p-3 text-red-800">{error}</p>:null}
    {notice?<p role="status" className="my-4 rounded-lg bg-emerald-50 p-3 text-emerald-800">{notice}</p>:null}
    {!draft&&!creating&&!statusReview?<button className="btn secondary mb-4" disabled={busy} onClick={()=>setRetry(value=>value+1)}>Refresh user information</button>:null}
    {profile?<section aria-label="My basic information" className="panel mb-5"><h2 className="text-lg font-semibold">My basic information</h2><p className="my-2">{profile.name} · {roles[profile.role]} · {profile.id}</p><p>Phone: {profile.phone||"Not provided"}</p><p>Email: {profile.email||"Not provided"}</p></section>:null}
    {admin&&!draft&&!creating&&!statusReview?<button className="btn mb-4" disabled={busy||loading} onClick={()=>{setError("");setNotice("");setCreating("patient");}}>Add patient</button>:null}
    {admin&&!draft&&!creating&&!statusReview?<button className="btn secondary mb-4 ml-3" disabled={busy||loading} onClick={()=>{setError("");setNotice("");setCreating("doctor");}}>Add doctor</button>:null}
    {admin&&!draft&&!creating&&!statusReview?<button className="btn secondary mb-4 ml-3" disabled={busy||loading} onClick={()=>{setError("");setNotice("");setCreating("staff");}}>Add staff</button>:null}
    {admin&&creating?<AddUser role={creating} api={api} busy={busy} onBusy={value=>{saving.current=value;epoch.current++;setBusy(value);}} onClose={()=>setCreating(null)} onSaved={user=>{setUsers(rows=>[...rows.filter(row=>row.id!==user.id),user]);setCreating(null);setQuery("");setRole(user.role);setNotice(`${user.role==="staff"?"Staff":user.role==="doctor"?"Doctor":"Patient"} added: ${user.name} · ${user.id}. ${user.role==="doctor"?"Staff can now configure the doctor profile and schedule.":user.role==="staff"?"Available in the operational staff selector.":"Available in the demo patient selector."}`);}}/>:null}
    {!admin?<p className="panel">Only Admin Demo can view the user directory or edit basic information. You can view your own information above.</p>:<>
      <section aria-label="User directory filters" className="panel mb-5"><div className="flex flex-wrap gap-5"><label className="grow">Search users<input aria-label="Search users" placeholder="Name, user ID, phone or email" maxLength={100} className="mt-2 block w-full rounded-lg border p-3" value={query} onChange={event=>setQuery(event.target.value)}/></label><label>Role<select aria-label="Filter user role" className="mt-2 block rounded-lg border p-3" value={role} onChange={event=>setRole(event.target.value as keyof typeof roles)}>{Object.entries(roles).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div><p className="muted mt-3">Showing {visible.length} of {users.length} users. Roles and user IDs stay fixed.</p></section>
      {statusReview?<section aria-label="Review staff status" className="panel mb-5"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">Review {statusReview.original.active?"staff deactivation":"staff reactivation"}</h2>
        <p className="my-3">{statusReview.name} · {statusReview.original.staff_id}</p><p>Current: {statusReview.original.active?"Active":"Inactive"} → New: {statusReview.original.active?"Inactive":"Active"}</p>
        <p className="muted my-3">{statusReview.original.active?"This staff identity will be removed from operational selectors, and its API requests will be rejected. Open forms close when the staff list refreshes.":"This staff identity will become available in operational selectors again."} Existing bookings, schedules, clinical records and previous staff actions are retained.</p>
        {statusChanged?<p role="alert" className="my-3 text-red-800">Staff status changed. Cancel and review the latest status.</p>:null}
        <button className="btn" disabled={busy||statusChanged||!!error} onClick={saveStatus}>{busy?"Saving…":statusReview.original.active?"Confirm deactivate staff":"Confirm reactivate staff"}</button>
        <button className="btn secondary ml-3" disabled={busy} onClick={()=>{setStatusReview(null);setError("");}}>Cancel staff status change</button>
      </section>:null}
      {draft?<section aria-label="Edit user information" className="panel mb-5"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{draft.review?"Review user information":"Edit user information"}</h2><p className="my-3">{draft.original.id} · {roles[draft.original.role]} · version {draft.original.version}</p>
        {changed?<p role="alert" className="my-3 text-red-800">This user information changed. Cancel and reopen the latest record before confirming.</p>:null}
        {draft.review?<><dl>{fields.map(field=><div key={field.key} className="my-3 rounded-lg bg-[#f4f7f6] p-3"><dt className="font-semibold">{field.label}</dt><dd className="break-words">Previous: {draft.original[field.key]||"Not provided"}</dd><dd className="break-words">New: {draft[field.key]||"Not provided"}</dd></div>)}</dl><p className="muted my-3">Updates basic information for the same user ID. Existing bookings and clinical records remain linked. Saved historical messages keep their original text.</p><button className="btn" disabled={busy||changed||!!error} onClick={save}>{busy?"Saving…":"Confirm user information"}</button><button className="btn secondary ml-3" disabled={busy||changed} onClick={()=>{setError("");setDraft({...draft,review:false});}}>Keep editing</button></>:<fieldset disabled={busy||changed}>{fields.map(field=><label key={field.key} className="my-3 block font-semibold">{field.label}<input aria-label={`Edit ${field.label.toLowerCase()}`} maxLength={field.max} type={field.key==="email"?"email":field.key==="phone"?"tel":"text"} className="mt-2 block w-full rounded-lg border p-3 font-normal" value={draft[field.key]} onChange={event=>{setError("");setDraft({...draft,[field.key]:event.target.value});}}/></label>)}<button className="btn" onClick={review}>Review user information</button></fieldset>}
        <button className="btn secondary mt-4" disabled={busy} onClick={()=>{setDraft(null);setError("");}}>Cancel user editing</button>
      </section>:null}
      <section aria-label="User directory" className="grid gap-4 md:grid-cols-2">{visible.map(user=><article key={user.id} className="panel min-w-0"><h2 className="break-words text-lg font-semibold">{user.name}</h2><p className="muted my-2">{roles[user.role]} · {user.id}</p><p className="break-words">Phone: {user.phone||"Not provided"}</p><p className="break-words">Email: {user.email||"Not provided"}</p><p className="muted my-3 text-sm">{user.updated_at?`Updated ${visitTime(user.updated_at)} · version ${user.version}`:"No edits recorded"}</p><button className="btn secondary" disabled={busy||!!draft||!!creating||!!statusReview} onClick={()=>{setError("");setNotice("");setDraft({original:user,name:user.name,phone:user.phone,email:user.email,review:false});}}>Edit {user.name}</button>{user.role==="staff"?(()=>{const status=statuses.find(row=>row.staff_id===user.id);return status?<><p className="my-3 font-semibold">Staff status: {status.active?"Active":"Inactive"}</p>{status.updated_at?<p className="muted my-2 text-sm">Status changed {visitTime(status.updated_at)} · {status.updated_by} · version {status.version}</p>:null}<button className="btn secondary" disabled={busy||!!draft||!!creating||!!statusReview} onClick={()=>{setError("");setNotice("");setStatusReview({original:status,name:user.name,request:crypto.randomUUID()});}}>{status.active?"Deactivate":"Reactivate"} {user.name}</button></>:<p className="muted mt-3 text-sm">{user.id==="staff-demo"?"Original demo identity · status protected":"Staff status is refreshing…"}</p>;})():null}</article>)}</section>
      {!loading&&!visible.length?<p className="panel">No matching users. Change the search or role filter.</p>:null}
    </>}
  </main>;
}
