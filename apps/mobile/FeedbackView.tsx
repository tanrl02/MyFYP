import React, { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { Booking, DemoApi, VisitFeedback, queueToken, visitTime } from "@smart-skin/shared";
export default function FeedbackView({api,bookings,onBusy}:{api:DemoApi;bookings:Booking[];onBusy:(value:boolean)=>void}){
  const [loadError,setLoadError]=useState("");
  const [records,setRecords]=useState<VisitFeedback[]>([]),[visit,setVisit]=useState<Booking|null>(null),[editing,setEditing]=useState<VisitFeedback|null>(null);
  const [rating,setRating]=useState(0),[comment,setComment]=useState(""),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[loading,setLoading]=useState(true),[notice,setNotice]=useState("");
  useEffect(()=>{
    if(busy)return;
    let active=true,fetching=false;
    async function load(){if(fetching)return;fetching=true;try{const data=await api.feedback();if(active){setRecords(data);setLoadError("");setLoading(false);}}catch(e){if(active){setLoadError(e instanceof Error?e.message:"Cannot load feedback.");setLoading(false);}}finally{fetching=false;}}
    void load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};
  },[api,busy]);
  const expired=!!editing&&Date.now()>=Date.parse(editing.edit_deadline);
  async function save(){
    if(!visit||!rating||busy)return;
    setBusy(true);onBusy(true);setError("");
    try{
      const saved=editing?await api.editFeedback(visit.id,rating,comment,editing.version):await api.submitFeedback(visit.id,rating,comment);
      setRecords(old=>[saved,...old.filter(r=>r.id!==saved.id)]);setVisit(null);setEditing(null);setConfirm(false);setNotice(editing?"Feedback updated. Staff can see your latest rating and comment.":"Feedback submitted.");
    }catch(e){setConfirm(false);setError(e instanceof Error?e.message:"Cannot save feedback.");}
    finally{setBusy(false);onBusy(false);}
  }
  function open(booking:Booking,saved:VisitFeedback|null){setVisit(booking);setEditing(saved);setRating(saved?.rating||0);setComment(saved?.comment||"");setConfirm(false);setError("");setNotice("");}
  const button=(label:string,action:()=>void,disabled=busy)=><Pressable accessibilityRole="button" disabled={disabled} onPress={action} style={{padding:12,marginTop:10,borderRadius:10,backgroundColor:disabled?"#dce5df":"#176f5e"}}><Text style={{color:"white",fontWeight:"600"}}>{label}</Text></Pressable>;
  const eligible=bookings.filter(b=>b.status==="completed"&&!records.some(r=>r.booking_id===b.id));
  return <View style={{marginBottom:20}}>
    <Text style={{fontSize:19,fontWeight:"600",color:"#19352e"}}>Visit feedback</Text>
    <Text style={{color:"#637970",marginVertical:10}}>Rate a completed visit. You can edit your feedback for 24 hours after its original submission. Staff see the latest rating and comment. Use fictional comments in this demo; do not include medical or personal details.</Text>
    {error||loadError?<Text accessibilityRole="alert" style={{color:"#9f2929"}}>{error||loadError}</Text>:null}
    {notice?<Text accessibilityLiveRegion="polite" style={{color:"#176f5e",marginVertical:10}}>{notice}</Text>:null}
    {visit?<View style={{padding:16,backgroundColor:"white",borderRadius:14}}>
      <Text style={{fontWeight:"600"}}>{editing?"Edit feedback":"New feedback"}</Text><Text>{queueToken(visit)} · {visit.doctor_name} · {visitTime(visit.starts_at)}</Text>
      {editing?<Text style={{marginTop:10}}>Editing closes {visitTime(editing.edit_deadline)} (Malaysia time). The original submission time stays unchanged.</Text>:null}
      {expired?<Text accessibilityRole="alert" style={{color:"#9f2929",marginTop:10}}>The 24-hour editing window has closed. Cancel to view your saved feedback.</Text>:null}
      <Text style={{marginTop:12}}>Rating: {rating||"Choose 1–5"} / 5</Text>
      <View style={{flexDirection:"row",gap:8}}>{[1,2,3,4,5].map(n=><Pressable key={n} accessibilityRole="button" accessibilityLabel={`Rate ${n} out of 5`} accessibilityState={{selected:rating===n,disabled:busy||confirm||expired}} disabled={busy||confirm||expired} onPress={()=>setRating(n)} style={{padding:14,backgroundColor:rating===n?"#176f5e":"#e7efeb",borderRadius:8}}><Text style={{color:rating===n?"white":"#176f5e"}}>{n}</Text></Pressable>)}</View>
      <Text style={{marginTop:12}}>Comment (optional, up to 1000 characters)</Text><TextInput accessibilityLabel="Feedback comment" multiline maxLength={1000} editable={!busy&&!confirm&&!expired} value={comment} onChangeText={setComment} style={{borderWidth:1,borderColor:"#dce6e0",padding:12,minHeight:85,marginTop:8,borderRadius:8}}/>
      {confirm?<><Text style={{marginTop:12}}>{editing?"Update":"Submit"} {rating}/5 and this comment for staff?</Text><Text style={{marginTop:8}}>{comment.trim()||"No comment added."}</Text>{button(busy?"Saving…":editing?"Confirm feedback update":"Confirm feedback",save,busy||expired)}{button("Keep editing",()=>setConfirm(false))}</>:button(editing?"Review feedback update":"Review feedback",()=>setConfirm(true),busy||!rating||expired||!!editing&&rating===editing.rating&&comment.trim()===editing.comment)}
      {button("Cancel feedback",()=>{setVisit(null);setEditing(null);setConfirm(false);setError("");})}
    </View>:!loading&&!loadError?eligible.map(b=><View key={b.id} style={{marginVertical:8}}><Text>{b.doctor_name} · {visitTime(b.starts_at)}</Text>{button(`Give feedback ${queueToken(b)} · ${visitTime(b.starts_at)}`,()=>open(b,null))}</View>):loading?<Text>Loading feedback…</Text>:null}
    {records.map(r=><View key={r.id} style={{padding:16,backgroundColor:"white",borderRadius:14,marginTop:12}}>
      <Text style={{fontWeight:"600"}}>{queueToken(r.visit)} · {r.visit.doctor_name} · {visitTime(r.visit.starts_at)}</Text><Text style={{marginTop:8}}>Submitted rating: {r.rating}/5</Text><Text style={{marginTop:8}}>{r.comment||"No comment added."}</Text>
      <Text style={{marginTop:8,color:"#637970"}}>Submitted {visitTime(r.created_at)}{r.edited_at?` · Edited ${visitTime(r.edited_at)}`:""}</Text>
      {Date.now()<Date.parse(r.edit_deadline)?<>{button(`Edit feedback ${queueToken(r.visit)} · ${visitTime(r.visit.starts_at)}`,()=>open(r.visit,r),busy||!!visit||!!loadError)}<Text style={{marginTop:8,color:"#637970"}}>Editing closes {visitTime(r.edit_deadline)} (Malaysia time).</Text></>:<Text style={{marginTop:8,color:"#637970"}}>The 24-hour editing window has closed.</Text>}
    </View>)}
    {!loading&&!visit&&!eligible.length&&!records.length&&!loadError?<Text>Feedback becomes available after a completed visit.</Text>:null}
  </View>;
}
