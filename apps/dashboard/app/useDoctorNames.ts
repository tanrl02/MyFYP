"use client";
import {useEffect,useState} from "react";
import {DemoApi,DemoDoctor,doctorNames as initialNames} from "@smart-skin/shared";

export default function useDoctorNames(){
  const [names,setNames]=useState<Record<DemoDoctor,string>>(initialNames);
  useEffect(()=>{let active=true,fetching=false;
    const api=new DemoApi(process.env.NEXT_PUBLIC_API_URL||"http://127.0.0.1:8000","staff-demo");
    async function load(){if(fetching)return;fetching=true;try{const rows=await api.demoDoctors();if(active)setNames(Object.fromEntries(rows.map(row=>[row.id,row.name])) as Record<DemoDoctor,string>);}catch{/* Retain known demo identities until the next refresh. */}finally{fetching=false;}}
    void load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer);};
  },[]);
  return names;
}
