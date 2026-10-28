import React,{useEffect,useState} from "react";
import {Image,Pressable,StyleSheet,Text,View,useWindowDimensions} from "react-native";
import {AssessmentComparison,DemoApi,assessmentOrigin,visitTime} from "@smart-skin/shared";
import AssessmentResult from "./AssessmentResult";
export default function AssessmentComparisonView({api,id}:{api:DemoApi;id:string}){
  const [data,setData]=useState<AssessmentComparison|null>(null),[error,setError]=useState("");
  const [retry,setRetry]=useState(0),[loading,setLoading]=useState(true);const {width}=useWindowDimensions();
  useEffect(()=>{let active=true;setData(null);setError("");setLoading(true);api.assessmentComparison(id).then(value=>{if(active)setData(value);}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Comparison unavailable.");}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[api,id,retry]);
  return <View style={styles.box}><Text style={styles.title}>Assessment comparison</Text><Text style={styles.body}>Compare the same skin area using similar lighting and distance. Each AI result is independent. Scores cannot measure improvement or worsening; a doctor should assess changes.</Text>
    {loading?<Text style={styles.body}>Loading comparison…</Text>:null}{error?<View><Text accessibilityRole="alert">{error}</Text><Pressable accessibilityRole="button" onPress={()=>setRetry(value=>value+1)}><Text style={styles.link}>Retry comparison</Text></Pressable></View>:null}
    {data?<View style={{flexDirection:width>=720?"row":"column",gap:14}}>{([['previous','Previous assessment'],['current','Follow-up assessment']] as const).map(([key,label])=>{const item=data[key];return <View key={key} style={styles.column}><Text style={styles.title}>{label}</Text><Text style={styles.body}>{visitTime(item.created_at)} · {assessmentOrigin(item)} · {item.id.slice(0,8)}</Text>{item.photo_uri?<Image accessibilityLabel={label+" photo"} source={{uri:item.photo_uri}} style={styles.photo} resizeMode="contain"/>:null}<AssessmentResult assessment={item}/></View>;})}</View>:null}
  </View>;
}
const styles=StyleSheet.create({box:{marginVertical:16},title:{fontSize:17,fontWeight:"600",color:"#19352e",marginVertical:8},body:{fontSize:13,lineHeight:20,color:"#52665e",marginBottom:10},column:{flex:1,minWidth:0,backgroundColor:"#f4f7f6",padding:12,borderRadius:12},photo:{width:"100%",height:200},link:{color:"#176f5e",fontWeight:"600",paddingVertical:10}});
