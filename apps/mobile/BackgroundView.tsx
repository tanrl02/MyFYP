import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { DemoApi, PatientBackground, visitTime } from "@smart-skin/shared";

const fields = [{key:"allergies",label:"Allergies"},{key:"medicines",label:"Current medicines"},{key:"conditions",label:"Existing conditions"}] as const;
export default function BackgroundView({api}:{api:DemoApi}) {
  const [saved,setSaved]=useState<PatientBackground|null>(null);
  const [draft,setDraft]=useState({allergies:"",medicines:"",conditions:""});
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  useEffect(()=>{let active=true;api.background().then(data=>{if(active){setSaved(data);setDraft(data);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[api]);
  async function reload(){
    setBusy(true);setError("");setNotice("");
    try{const data=await api.background();setSaved(data);setDraft(data);setConfirm(false);}catch(e){setError(e instanceof Error?e.message:"Cannot load background.");}finally{setBusy(false);}
  }
  async function save(){
    if(!saved||busy)return;setBusy(true);setError("");setNotice("");
    try{const data=await api.saveBackground({...draft,version:saved.version});setSaved(data);setDraft(data);setConfirm(false);setNotice("Medical background saved.");}catch(e){setConfirm(false);setError(e instanceof Error?e.message:"Cannot save background.");}finally{setBusy(false);}
  }
  const changed=saved&&fields.some(f=>draft[f.key].trim()!==saved[f.key]);
  return <View style={s.card}><Text style={s.title}>My profile</Text><Text style={s.heading}>Medical background</Text><Text style={s.body}>Use fictional information for this demo. Your assigned doctor can read your latest background during consultation. Blank means not provided; write “None known” only if that is what you intend.</Text>
    {loading?<ActivityIndicator color="#176f5e"/>:null}
    {error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}
    {notice?<Text accessibilityRole="alert" style={s.notice}>{notice}</Text>:null}
    {saved?confirm?<><Text style={s.heading}>Review your background</Text>{fields.map(f=><View key={f.key}><Text style={s.label}>{f.label}</Text><Text style={s.body}>{draft[f.key].trim()||"Not provided"}</Text></View>)}<Text style={s.body}>Saving replaces your current background. Published consultation notes stay unchanged.</Text><Pressable accessibilityRole="button" disabled={busy} style={s.button} onPress={save}><Text style={s.buttonText}>{busy?"Saving…":"Confirm background"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={()=>setConfirm(false)}><Text style={s.link}>Keep editing</Text></Pressable></>:<>{fields.map(f=><View key={f.key}><Text style={s.label}>{f.label}</Text><TextInput accessibilityLabel={f.label} multiline maxLength={1000} editable={!busy} value={draft[f.key]} onChangeText={value=>{setDraft(d=>({...d,[f.key]:value}));setNotice("");}} placeholder="Not provided" style={s.input}/><Text style={s.count}>{draft[f.key].length}/1000</Text></View>)}<Pressable accessibilityRole="button" disabled={busy||!changed} style={[s.button,(busy||!changed)&&{opacity:.4}]} onPress={()=>setConfirm(true)}><Text style={s.buttonText}>Review background</Text></Pressable></>:null}
    {!loading?<Pressable accessibilityRole="button" disabled={busy} onPress={reload}><Text style={s.link}>{busy?"Please wait…":"Reload saved background (discard edits)"}</Text></Pressable>:null}
    {saved?<Text style={s.body}>{saved.updated_at?`Last saved ${visitTime(saved.updated_at)} · patient-provided` : "No medical background saved yet."}</Text>:null}
  </View>;
}
const s=StyleSheet.create({card:{padding:20,backgroundColor:"#fff",borderWidth:1,borderColor:"#dce6e0",borderRadius:16},title:{fontSize:23,fontWeight:"700",color:"#19352e"},heading:{fontSize:17,fontWeight:"600",color:"#19352e",marginTop:16},body:{fontSize:13,lineHeight:21,color:"#637970",marginVertical:10},label:{fontSize:14,fontWeight:"600",color:"#19352e",marginTop:14},input:{borderWidth:1,borderColor:"#ccdcd4",borderRadius:10,padding:12,minHeight:80,textAlignVertical:"top",color:"#19352e",marginTop:8},count:{fontSize:11,color:"#637970",textAlign:"right",marginTop:4},button:{backgroundColor:"#176f5e",padding:14,borderRadius:10,alignItems:"center",marginTop:18},buttonText:{color:"#fff",fontWeight:"600"},link:{color:"#176f5e",fontWeight:"600",fontSize:13,paddingVertical:12},error:{color:"#9f2929",padding:12,backgroundColor:"#fff0f0",marginTop:12},notice:{color:"#176f5e",padding:12,backgroundColor:"#e7f4ed",marginTop:12}});
