"use client";
import {createContext,useContext,useEffect,useMemo,useRef,useState} from "react";
import {usePathname} from "next/navigation";
import {DemoApi,DemoStaff} from "@smart-skin/shared";

const initialNames:Record<DemoStaff,string>={"staff-demo":"Staff Demo"};
const StaffContext=createContext<{actor:DemoStaff;names:Record<DemoStaff,string>;selectStaff:(id:DemoStaff)=>void}>({actor:"staff-demo",names:initialNames,selectStaff:()=>{}});
export const useStaffIdentity=()=>useContext(StaffContext);
export default function StaffIdentity({children}:{children:React.ReactNode}){
  const path=usePathname(),[actor,setActor]=useState<DemoStaff>("staff-demo"),[names,setNames]=useState(initialNames),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const actorRef=useRef<DemoStaff>("staff-demo");
  const operational=path==="/"||path==="/doctors"||path==="/slots"||/^\/(stock|reports|feedback)(\/|$)/.test(path);
  useEffect(()=>{let active=true,fetching=false;const api=new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo");
    async function load(){
      if(fetching)return;fetching=true;
      try{const rows=await api.demoStaff();if(!active)return;
        setNames(Object.fromEntries(rows.map(row=>[row.id,row.name])) as Record<DemoStaff,string>);setError("");
        let selected=actorRef.current;try{selected=(sessionStorage.getItem('smart-skin-demo-staff') as DemoStaff)||selected;}catch{}
        if(!rows.some(row=>row.id===selected)){
          selected="staff-demo";setNotice("The previous staff identity is unavailable. Switched to Staff Demo; open forms were closed.");
          try{sessionStorage.removeItem('smart-skin-demo-staff');}catch{}
        }
        actorRef.current=selected;setActor(selected);
      }catch{if(active)setError("Staff identity list could not refresh. Retaining the current selection.");}finally{fetching=false;}
    }
    void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};
  },[]);
  function selectStaff(id:DemoStaff){if(!names[id])return;setError("");setNotice("");actorRef.current=id;setActor(id);try{sessionStorage.setItem('smart-skin-demo-staff',id);}catch{}}
  const value=useMemo(()=>({actor,names,selectStaff}),[actor,names]);
  return <StaffContext.Provider value={value}>{operational?<section aria-label="Operational staff identity" className="mx-auto mt-4 max-w-6xl rounded-xl border border-[#ccdcd4] bg-white p-4">
    <label className="font-semibold">Staff demo identity<select aria-label="Staff demo identity" className="ml-3 rounded-lg border p-2" value={actor} onChange={event=>selectStaff(event.target.value as DemoStaff)}>{Object.entries(names).map(([id,name])=><option key={id} value={id}>{name}{id!=="staff-demo"?` · ${id.slice(-6)}`:""}</option>)}</select></label>
    <p className="muted mt-2 text-sm">Demo only; not secure login. This staff identity is used across operational pages. Switching staff closes open forms.</p>
  </section>:null}{error||notice?<p role="alert" className="mx-auto my-3 max-w-6xl rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{error||notice}</p>:null}<div key={operational?actor:'mixed-roles'}>{children}</div></StaffContext.Provider>;
}
