import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, AppState, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import CareView from "./CareView";
import SkinView from "./SkinView";
import VisitNotes from "./VisitNotes";
import FeedbackView from "./FeedbackView";
import RescheduleView from "./RescheduleView";
import { Booking, DemoApi, DemoPatient, Slot, patientNames, queueToken, statusLabels, visitTime } from "@smart-skin/shared";
import { apiBase as base } from "./apiConfig";
export default function App() {
  const [patient,setPatient]=useState<DemoPatient>("patient-ava");
  const api=useMemo(()=>new DemoApi(base,patient),[patient]);
  const [tab,setTab]=useState<"book"|"visits"|"care"|"skin">("book");
  const [slots,setSlots]=useState<Slot[]>([]),[bookings,setBookings]=useState<Booking[]>([]);
  const [selected,setSelected]=useState<Slot|null>(null),[cancelId,setCancelId]=useState<string|null>(null);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  const [requestId,setRequestId]=useState("");
  const [moving,setMoving]=useState<Booking|null>(null);
  const refresh=useCallback(async()=>{ const [s,b]=await Promise.all([api.slots(),api.bookings()]);setSlots(s);setBookings(b);setError(""); },[api]);
  useEffect(()=>{
    let active=true, fetching=false;
    setSelected(null);setCancelId(null);setMoving(null);setBookings([]);setNotice("");setLoading(true);
    const load=async()=>{if(fetching)return;fetching=true;try{const [s,b]=await Promise.all([api.slots(),api.bookings()]);if(active){setSlots(s);setBookings(b);setError("");}}catch(e){if(active)setError(e instanceof Error ? e.message : "Unable to load.");}finally{fetching=false;if(active)setLoading(false);}};
    void load(); const timer=setInterval(load,3000); const subscription=AppState.addEventListener("change",state=>{if(state==="active")void load();});
    return()=>{active=false;clearInterval(timer);subscription.remove();};
  },[api]);
  const act=async(fn:()=>Promise<Booking>, message:string)=>{
    if(busy)return;setBusy(true);setError("");setNotice("");
    try{await fn();setSelected(null);setCancelId(null);setNotice(message);setTab("visits");await refresh();}catch(e){setError(e instanceof Error ? e.message : "Please retry.");}finally{setBusy(false);}
  };
  function choose(slot:Slot){setSelected(slot);setNotice("");setRequestId(`booking-${Date.now()}-${Math.random().toString(36).slice(2)}`);}
  return <SafeAreaView style={styles.screen}><StatusBar style="dark"/><ScrollView contentContainerStyle={styles.content}>
    <View style={styles.header}><View><Text style={styles.logo}>Smart Skin</Text><Text style={styles.muted}>Your next visit, made simpler.</Text></View><Text style={styles.demoPill}>DEMO</Text></View>
    <View style={styles.warning}><Text style={styles.warningText}>Synthetic patient demo. This is not secure login. Do not enter real patient information.</Text></View>
    <Text style={styles.label}>DEMO PATIENT</Text><View style={styles.row}>{(Object.keys(patientNames) as DemoPatient[]).map(id=><Pressable key={id} accessibilityRole="button" disabled={busy} onPress={()=>setPatient(id)} style={[styles.patient,patient===id&&styles.activePatient]}><Text style={{color:patient===id?"#fff":"#176f5e",fontWeight:"600"}}>{patientNames[id]}</Text></Pressable>)}</View>
    <View style={[styles.row,{marginVertical:20}]}>{(["skin","book","visits","care"] as const).map(t=><Pressable accessibilityRole="button" disabled={busy} key={t} onPress={()=>{setTab(t);setSelected(null);setCancelId(null);setMoving(null);}} style={[styles.tab,tab===t&&styles.activeTab]}><Text style={[styles.tabText,tab===t&&{color:"#176f5e"}]}>{t==="skin"?"Skin check":t==="book"?"Book a visit":t==="visits"?"My visits":"Care & bills"}</Text></Pressable>)}</View>
    {error ? <View accessibilityRole="alert" style={styles.error}><Text style={{color:"#9f2929"}}>{error}</Text><Pressable accessibilityRole="button" onPress={()=>{setLoading(true);refresh().catch(e=>setError(e.message)).finally(()=>setLoading(false));}}><Text style={styles.link}>Retry connection</Text></Pressable></View>:null}
    {notice?<View style={styles.success}><Text style={{color:"#176f5e"}}>{notice}</Text></View>:null}
    {loading?<ActivityIndicator color="#176f5e"/>:null}
    {tab==="skin"?<SkinView key={patient} patient={patient}/>:tab==="care"?<CareView key={patient} patient={patient}/>:tab==="book"?<>
      <Text style={styles.title}>{selected?"Confirm your visit":"Find a consultation"}</Text><Text style={[styles.muted,{marginBottom:18}]}>Times shown in Malaysia time. Each demo slot has two places.</Text>
      {selected?<View style={styles.card}><Text style={styles.cardTitle}>{selected.doctor_name}</Text><Text style={styles.muted}>{visitTime(selected.starts_at)}</Text><Text style={styles.body}>Confirming saves a shared booking and issues your queue number.</Text><Pressable accessibilityRole="button" disabled={busy} style={[styles.button,busy&&styles.disabled]} onPress={()=>act(()=>api.book(selected.id,requestId),"Your visit is booked. Staff can now see it in the shared queue.")}><Text style={styles.buttonText}>{busy?"Saving…":"Confirm booking"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={styles.quietButton} onPress={()=>setSelected(null)}><Text style={styles.link}>Back to available times</Text></Pressable></View>:slots.map(s=>{const duplicate=bookings.some(b=>b.slot_id===s.id&&b.status!=="cancelled");return <View style={styles.card} key={s.id}><View style={styles.between}><Text style={styles.cardTitle}>{s.doctor_name}</Text><Text style={styles.available}>{s.available} places</Text></View><Text style={styles.muted}>{visitTime(s.starts_at)}</Text><Pressable accessibilityRole="button" disabled={busy||s.available===0||duplicate} style={[styles.button,(s.available===0||duplicate)&&styles.disabled]} onPress={()=>choose(s)}><Text style={styles.buttonText}>{duplicate?"Already booked":s.available===0?"Slot full":"Select time"}</Text></Pressable></View>})}
      {!loading&&!selected&&slots.length===0?<Text style={styles.muted}>No available slots. Retry when the API is reachable.</Text>:null}
    </>:<>
      <View style={styles.between}><Text style={styles.title}>My visits</Text><Pressable accessibilityRole="button" onPress={()=>refresh().catch(e=>setError(e.message))}><Text style={styles.link}>Refresh</Text></Pressable></View><Text style={[styles.muted,{marginBottom:18}]}>Queue changes refresh every few seconds.</Text>
      {moving?<RescheduleView key={moving.id} api={api} booking={moving} slots={slots} busy={busy} onBusy={setBusy} onClose={()=>setMoving(null)} onSaved={saved=>{setMoving(null);setNotice(`Visit rescheduled: ${queueToken(saved)} · ${saved.doctor_name} · ${visitTime(saved.starts_at)}.`);void refresh().catch(e=>setError(e.message));}}/>:null}
      {bookings.map(b=><View key={b.id} style={styles.card}><View style={styles.between}><Text style={styles.queue}>{queueToken(b)}</Text><Text style={styles.status}>{b.rescheduled_to_id?"Rescheduled":statusLabels[b.status]}</Text></View><Text style={styles.cardTitle}>{b.doctor_name}</Text><Text style={styles.muted}>{visitTime(b.starts_at)}</Text>{b.status==="waiting"?(cancelId===b.id?<><Text style={styles.body}>Cancel this visit and release your place?</Text><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={()=>act(()=>api.cancel(b.id),"Visit cancelled. Your slot is available again.")}><Text style={styles.buttonText}>{busy?"Saving…":"Confirm cancellation"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={()=>setCancelId(null)}><Text style={styles.link}>Keep my booking</Text></Pressable></>:<><Pressable accessibilityRole="button" disabled={busy||!!moving} style={styles.quietButton} onPress={()=>setCancelId(b.id)}><Text style={styles.link}>Cancel visit</Text></Pressable>{new Date(b.starts_at).getTime()>Date.now()?<Pressable accessibilityRole="button" disabled={busy||!!moving} style={styles.quietButton} onPress={()=>{setMoving(b);setCancelId(null);setNotice("");}}><Text style={styles.link}>Reschedule {queueToken(b)}</Text></Pressable>:null}</>):null}</View>)}
      {!loading&&bookings.length===0?<View style={styles.card}><Text style={styles.cardTitle}>No visits yet</Text><Text style={styles.body}>Choose Book a visit to select a doctor and time.</Text></View>:null}
      <VisitNotes key={patient} patient={patient}/>
      <FeedbackView key={`feedback-${patient}`} api={api} bookings={bookings}/>
    </>}
    <Text style={styles.footnote}>Shared skin assessment history, booking, queue, prescriptions and billing. AI results and payments are simulated; identities are demo only.</Text>
  </ScrollView></SafeAreaView>;
}
const styles=StyleSheet.create({
  screen:{flex:1,backgroundColor:"#f4f7f6"},content:{padding:22,paddingTop:36,paddingBottom:50,maxWidth:620,width:"100%",alignSelf:"center"},header:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:20},logo:{fontSize:25,fontWeight:"700",color:"#176f5e",marginBottom:4},muted:{fontSize:13,color:"#637970",lineHeight:20},demoPill:{fontSize:11,fontWeight:"700",color:"#176f5e",backgroundColor:"#e3eee8",padding:9,borderRadius:20},warning:{backgroundColor:"#fff3db",padding:14,borderRadius:12,marginBottom:20},warningText:{color:"#825b16",fontSize:12,lineHeight:18},label:{fontSize:11,fontWeight:"700",letterSpacing:1,color:"#637970",marginBottom:9},row:{flexDirection:"row",gap:10},patient:{padding:12,borderRadius:10,backgroundColor:"#e7efeb",flex:1,alignItems:"center"},activePatient:{backgroundColor:"#176f5e"},tab:{flex:1,padding:12,alignItems:"center",borderBottomWidth:2,borderBottomColor:"#dce5df"},activeTab:{borderBottomColor:"#176f5e"},tabText:{fontWeight:"600",color:"#637970"},title:{fontSize:23,fontWeight:"700",color:"#19352e",marginBottom:8},card:{padding:20,backgroundColor:"#fff",borderWidth:1,borderColor:"#dce6e0",borderRadius:16,marginBottom:14},cardTitle:{fontSize:16,fontWeight:"600",color:"#19352e",marginBottom:7},between:{flexDirection:"row",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"},available:{fontSize:12,color:"#176f5e"},button:{padding:14,borderRadius:10,backgroundColor:"#176f5e",alignItems:"center",marginTop:16},buttonText:{color:"#fff",fontWeight:"600"},disabled:{opacity:.4},quietButton:{paddingTop:14,paddingBottom:5,alignItems:"center"},link:{color:"#176f5e",fontWeight:"600",fontSize:13,paddingVertical:8},body:{color:"#637970",fontSize:13,lineHeight:21,marginTop:10},queue:{fontSize:27,fontWeight:"700",color:"#176f5e",marginBottom:12},status:{fontSize:12,color:"#637970",maxWidth:210},error:{backgroundColor:"#fff0f0",padding:14,borderRadius:12,marginBottom:16},success:{backgroundColor:"#e7f4ed",padding:14,borderRadius:12,marginBottom:16},footnote:{color:"#637970",fontSize:11,lineHeight:18,marginTop:15}
});
