import React,{useEffect,useState} from "react";
import {ActivityIndicator,AppState,Pressable,StyleSheet,Text,View} from "react-native";
import {DemoApi,UserProfile,visitTime} from "@smart-skin/shared";

export default function BasicInformation({api}:{api:DemoApi}){
  const [profile,setProfile]=useState<UserProfile|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true,fetching=false;setProfile(null);setError("");setLoading(true);
    async function load(){if(fetching)return;fetching=true;try{const saved=await api.me();if(active){setProfile(saved);setError("");}}catch(e){if(active)setError(e instanceof Error?e.message:"Cannot load basic information.");}finally{fetching=false;if(active)setLoading(false);}}
    void load();const timer=setInterval(load,5000),subscription=AppState.addEventListener("change",state=>{if(state==="active")void load();});return()=>{active=false;clearInterval(timer);subscription.remove();};
  },[api,retry]);
  return <View style={s.card}><Text style={s.heading}>Basic information</Text><Text style={s.body}>Managed by the administrator. Contact the clinic if these details need correcting. Demo identity buttons keep their fixed demonstration labels.</Text>
    {loading?<ActivityIndicator color="#176f5e"/>:null}{error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}
    {profile?<><Text style={s.name}>{profile.name}</Text><Text style={s.body}>Phone: {profile.phone||"Not provided"}</Text><Text style={s.body}>Email: {profile.email||"Not provided"}</Text><Text style={s.body}>{profile.updated_at?`Updated ${visitTime(profile.updated_at)}`:"No edits recorded"}</Text></>:null}
    <Pressable accessibilityRole="button" onPress={()=>setRetry(value=>value+1)}><Text style={s.link}>Refresh basic information</Text></Pressable>
  </View>;
}
const s=StyleSheet.create({card:{padding:20,backgroundColor:"#fff",borderWidth:1,borderColor:"#dce6e0",borderRadius:16,marginBottom:14},heading:{fontSize:20,fontWeight:"700",color:"#19352e"},name:{fontSize:17,fontWeight:"600",color:"#19352e",marginVertical:8},body:{fontSize:13,lineHeight:21,color:"#637970",marginVertical:5},link:{fontSize:13,fontWeight:"600",color:"#176f5e",paddingVertical:12},error:{backgroundColor:"#fff0f0",padding:12,color:"#9f2929",borderRadius:10}});
