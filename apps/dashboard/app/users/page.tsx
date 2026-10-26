"use client";
import {useEffect,useMemo,useRef,useState} from "react";
import {DemoActor,DemoApi,UserProfile,visitTime} from "@smart-skin/shared";
import AddPatient from "./AddPatient";

const identities:Partial<Record<DemoActor,string>>={"admin-demo":"Admin Demo","staff-demo":"Staff Demo","doctor-lim":"Dr. Lim (demo)","doctor-anita":"Dr. Anita (demo)","patient-ava":"Ava Demo","patient-noah":"Noah Demo"};
const roles={all:"All roles",patient:"Patient",doctor:"Doctor",staff:"Staff",admin:"Admin"} as const;
const fields=[{key:"name",label:"Name",max:100},{key:"phone",label:"Phone",max:30},{key:"email",label:"Email",max:254}] as const;
type Draft={original:UserProfile;name:string;phone:string;email:string;review:boolean};
export default function UsersPage(){
  const [creating,setCreating]=useState(false);
  const [actor,setActor]=useState<DemoActor>("admin-demo");
  const api=useMemo(()=>new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000",actor),[actor]);
  const admin=actor==="admin-demo";
  const [users,setUsers]=useState<UserProfile[]>([]),[own,setOwn]=useState<{actor:DemoActor;profile:UserProfile}|null>(null);
  const [query,setQuery]=useState(""),[role,setRole]=useState<keyof typeof roles>("all");
  const [draft,setDraft]=useState<Draft|null>(null),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [error,setError]=useState(""),[notice,setNotice]=useState(""),[retry,setRetry]=useState(0);
  const epoch=useRef(0),saving=useRef(false),heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{
    let active=true,fetching=false;setUsers([]);setOwn(null);setDraft(null);setCreating(false);setQuery("");setRole("all");setError("");setNotice("");setLoading(true);
    async function load(){if(fetching||saving.current)return;fetching=true;const revision=epoch.current;
      try{const [profile,list]=await Promise.all([api.me(),actor==="admin-demo"?api.users():Promise.resolve([])]);if(active&&revision===epoch.current){setOwn({actor,profile});setUsers(list);setError("");}}
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
  const profile=own?.actor===actor?own.profile:null;
  return <main className="mx-auto max-w-6xl p-6 md:p-10">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4"><div><p className="eyebrow">Smart Skin</p><h1 className="text-3xl font-semibold">User management</h1></div><nav className="flex gap-5 text-sm"><a className="underline" href="/doctors">Doctor specialty & expertise</a><a className="underline" href="/">Patient queue</a></nav></header>
    <p className="muted my-4">Synthetic demonstration only. Demo identity selection is not secure login. Use fictional contact details. Admin manages basic user information; clinical records are excluded.</p>
    <label className="mb-5 block font-semibold">Demo identity<select aria-label="Demo identity" className="ml-3 rounded-lg border p-2" value={actor} disabled={busy} onChange={event=>setActor(event.target.value as DemoActor)}>{Object.entries(identities).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
    {loading?<p role="status">Loading user information…</p>:null}
    {error?<p role="alert" className="my-4 rounded-lg bg-red-50 p-3 text-red-800">{error}</p>:null}
    {notice?<p role="status" className="my-4 rounded-lg bg-emerald-50 p-3 text-emerald-800">{notice}</p>:null}
    {!draft&&!creating?<button className="btn secondary mb-4" disabled={busy} onClick={()=>setRetry(value=>value+1)}>Refresh user information</button>:null}
    {profile?<section aria-label="My basic information" className="panel mb-5"><h2 className="text-lg font-semibold">My basic information</h2><p className="my-2">{profile.name} · {roles[profile.role]} · {profile.id}</p><p>Phone: {profile.phone||"Not provided"}</p><p>Email: {profile.email||"Not provided"}</p></section>:null}
    {admin&&!draft&&!creating?<button className="btn mb-4" disabled={busy||loading} onClick={()=>{setError("");setNotice("");setCreating(true);}}>Add patient</button>:null}
    {admin&&creating?<AddPatient api={api} busy={busy} onBusy={value=>{saving.current=value;epoch.current++;setBusy(value);}} onClose={()=>setCreating(false)} onSaved={user=>{setUsers(rows=>[...rows.filter(row=>row.id!==user.id),user]);setCreating(false);setQuery("");setRole("patient");setNotice(`Patient added: ${user.name} · ${user.id}. Available in the demo patient selector.`);}}/>:null}
    {!admin?<p className="panel">Only Admin Demo can view the user directory or edit basic information. You can view your own information above.</p>:<>
      <section aria-label="User directory filters" className="panel mb-5"><div className="flex flex-wrap gap-5"><label className="grow">Search users<input aria-label="Search users" placeholder="Name, user ID, phone or email" maxLength={100} className="mt-2 block w-full rounded-lg border p-3" value={query} onChange={event=>setQuery(event.target.value)}/></label><label>Role<select aria-label="Filter user role" className="mt-2 block rounded-lg border p-3" value={role} onChange={event=>setRole(event.target.value as keyof typeof roles)}>{Object.entries(roles).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div><p className="muted mt-3">Showing {visible.length} of {users.length} users. Roles and user IDs stay fixed.</p></section>
      {draft?<section aria-label="Edit user information" className="panel mb-5"><h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{draft.review?"Review user information":"Edit user information"}</h2><p className="my-3">{draft.original.id} · {roles[draft.original.role]} · version {draft.original.version}</p>
        {changed?<p role="alert" className="my-3 text-red-800">This user information changed. Cancel and reopen the latest record before confirming.</p>:null}
        {draft.review?<><dl>{fields.map(field=><div key={field.key} className="my-3 rounded-lg bg-[#f4f7f6] p-3"><dt className="font-semibold">{field.label}</dt><dd className="break-words">Previous: {draft.original[field.key]||"Not provided"}</dd><dd className="break-words">New: {draft[field.key]||"Not provided"}</dd></div>)}</dl><p className="muted my-3">Updates basic information for the same user ID. Existing bookings and clinical records remain linked. Saved historical messages keep their original text.</p><button className="btn" disabled={busy||changed||!!error} onClick={save}>{busy?"Saving…":"Confirm user information"}</button><button className="btn secondary ml-3" disabled={busy||changed} onClick={()=>{setError("");setDraft({...draft,review:false});}}>Keep editing</button></>:<fieldset disabled={busy||changed}>{fields.map(field=><label key={field.key} className="my-3 block font-semibold">{field.label}<input aria-label={`Edit ${field.label.toLowerCase()}`} maxLength={field.max} type={field.key==="email"?"email":field.key==="phone"?"tel":"text"} className="mt-2 block w-full rounded-lg border p-3 font-normal" value={draft[field.key]} onChange={event=>{setError("");setDraft({...draft,[field.key]:event.target.value});}}/></label>)}<button className="btn" onClick={review}>Review user information</button></fieldset>}
        <button className="btn secondary mt-4" disabled={busy} onClick={()=>{setDraft(null);setError("");}}>Cancel user editing</button>
      </section>:null}
      <section aria-label="User directory" className="grid gap-4 md:grid-cols-2">{visible.map(user=><article key={user.id} className="panel min-w-0"><h2 className="break-words text-lg font-semibold">{user.name}</h2><p className="muted my-2">{roles[user.role]} · {user.id}</p><p className="break-words">Phone: {user.phone||"Not provided"}</p><p className="break-words">Email: {user.email||"Not provided"}</p><p className="muted my-3 text-sm">{user.updated_at?`Updated ${visitTime(user.updated_at)} · version ${user.version}`:"No edits recorded"}</p><button className="btn secondary" disabled={busy||!!draft||creating} onClick={()=>{setError("");setNotice("");setDraft({original:user,name:user.name,phone:user.phone,email:user.email,review:false});}}>Edit {user.name}</button></article>)}</section>
      {!loading&&!visible.length?<p className="panel">No matching users. Change the search or role filter.</p>:null}
    </>}
  </main>;
}
