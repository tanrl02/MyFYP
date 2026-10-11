import React, { useEffect, useMemo, useState } from "react";
import { Text, View } from "react-native";
import { Consultation, DemoApi, DemoPatient, queueToken, visitTime } from "@smart-skin/shared";
import { apiBase } from "./apiConfig";

export default function VisitNotes({ patient }: { patient: DemoPatient }) {
  const api = useMemo(() => new DemoApi(apiBase,patient),[patient]);
  const [records,setRecords] = useState<Consultation[]>([]), [error,setError] = useState("");
  useEffect(() => {
    let active=true, fetching=false;
    async function load() {
      if(fetching)return; fetching=true;
      try { const data=await api.consultations(); if(active){setRecords(data);setError("");} }
      catch(e){if(active)setError(e instanceof Error?e.message:"Cannot load consultation notes.");}
      finally{fetching=false;}
    }
    void load(); const timer=setInterval(load,3000);
    return()=>{active=false;clearInterval(timer);};
  },[api]);
  return <View style={{marginBottom:18}}><Text style={{fontSize:19,fontWeight:"600",color:"#19352e",marginBottom:10}}>Published consultation notes</Text>
    {error?<Text accessibilityRole="alert" style={{color:"#9f2929",padding:12}}>{error}</Text>:null}
    {records.map(({visit,note})=>note?<View key={visit.id} style={{backgroundColor:"white",padding:18,borderRadius:14,borderWidth:1,borderColor:"#dce6e0",marginBottom:12}}>
      <Text style={{fontWeight:"600",color:"#19352e"}}>{queueToken(visit)} · {visit.doctor_name} · {visitTime(visit.starts_at)}</Text>
      <Text style={{color:"#637970",marginVertical:10,fontSize:12}}>Published {visitTime(note.created_at)} · demo consultation</Text>
      <Text style={{fontWeight:"600",color:"#19352e"}}>Doctor findings</Text><Text style={{color:"#637970",lineHeight:21,marginVertical:8}}>{note.findings}</Text>
      <Text style={{fontWeight:"600",color:"#19352e"}}>Follow-up</Text><Text style={{color:"#637970",lineHeight:21,marginTop:8}}>{note.follow_up}</Text>
    </View>:null)}
    {!records.length&&!error?<Text style={{color:"#637970",fontSize:13,lineHeight:20}}>No published consultation notes yet. Your doctor can publish one when your visit is called.</Text>:null}
  </View>;
}
