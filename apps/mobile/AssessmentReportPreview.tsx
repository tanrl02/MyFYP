import React,{useEffect,useRef,useState} from "react";
import {Image,Platform,Pressable,Text,View} from "react-native";
import * as Print from "expo-print";
import {Directory,File} from "expo-file-system";
import {AssessmentReport,DemoApi,assessmentReportHtml,assessmentReportFilename,assessmentReportSections,assessmentReportSignature,assessmentReportNotice} from "@smart-skin/shared";

export default function AssessmentReportPreview({api,id}:{api:DemoApi;id:string}){
 const [report,setReport]=useState<AssessmentReport|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const active=useRef(true),frame=useRef<HTMLIFrameElement>(null),[ready,setReady]=useState(false);
 useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
 async function preview(){setBusy(true);setMessage("");setReady(false);try{const data=await api.assessmentReport(id);if(active.current)setReport(data);}catch(e){if(active.current){setReport(null);setMessage(e instanceof Error?e.message:"Report unavailable.");}}finally{if(active.current)setBusy(false);}}
 async function save(){if(!report||busy)return;setBusy(true);setMessage("");let cached:File|undefined;
  try{
   const fresh=await api.assessmentReport(id);if(!active.current)return;
   if(assessmentReportSignature(fresh)!==assessmentReportSignature(report)){setReady(false);setReport(fresh);setMessage("Report changed. Review the updated preview before exporting.");return;}
   if(Platform.OS==="web"){
    if(!ready||!frame.current?.contentWindow)throw new Error("Preview unavailable. Reopen the report.");
    frame.current.contentWindow.focus();frame.current.contentWindow.print();return;
   }
   const pdf=await Print.printToFileAsync({html:assessmentReportHtml(report),width:595,height:842});cached=new File(pdf.uri);if(!active.current)return;
   const folder=await Directory.pickDirectoryAsync();if(!active.current)return;
   const bytes=await cached.bytes();if(!active.current)return;
   const destination=folder.createFile(assessmentReportFilename(report),"application/pdf");
   try{await destination.write(bytes);}catch(error){if(destination.exists)destination.delete();throw error;}
   if(active.current)setMessage("PDF saved in your selected folder.");
  }catch(e){if(active.current)setMessage(e instanceof Error?`PDF not saved: ${e.message}`:"PDF not saved. You can try again.");}
  finally{try{if(cached?.exists)cached.delete();}catch{/* Cache cleanup must not leave the preview busy. */}if(active.current)setBusy(false);}
 }
 const button=(label:string,action:()=>void,disabled=false)=><Pressable accessibilityRole="button" disabled={disabled} onPress={action} style={{padding:12,borderWidth:1,borderColor:"#ccdcd4",borderRadius:8,opacity:disabled?.5:1,marginVertical:6}}><Text style={{color:"#225941",fontWeight:"600"}}>{label}</Text></Pressable>;
 return <View style={{marginVertical:14}}>{button(busy?"Preparing report…":report?"Refresh report preview":"Preview assessment report",preview,busy)}{message?<Text accessibilityLiveRegion="polite" style={{marginVertical:8}}>{message}</Text>:null}{report?<View><Text style={{color:"#52665e",marginVertical:10}}>{assessmentReportNotice}</Text>{Platform.OS==="web"?<iframe ref={frame} title="Assessment report preview" sandbox="allow-same-origin allow-modals" srcDoc={assessmentReportHtml(report)} onLoad={()=>setReady(true)} style={{width:"100%",height:600,border:"1px solid #ccdcd4"}}/>:<View style={{backgroundColor:"white",padding:16,borderWidth:1,borderColor:"#ccdcd4"}}><Text style={{fontWeight:"700",fontSize:22}}>Skin assessment report</Text><Text>Smart Skin FYP - demo / experimental system</Text>{report.assessment.photo_uri?<Image accessibilityLabel="Report assessment photo" source={{uri:report.assessment.photo_uri}} style={{width:"100%",height:190}} resizeMode="contain"/>:null}{assessmentReportSections(report).map((s,i)=><View key={i} style={{marginTop:16}}><Text style={{fontWeight:"700",fontSize:16}}>{s.title}</Text><Text style={{lineHeight:22,marginTop:6}}>{s.text}</Text></View>)}</View>}{button(Platform.OS==="web"?"Print / Save PDF":"Save PDF",save,busy||(Platform.OS==="web"&&!ready))}{button("Close report",()=>{setReport(null);setMessage("");},busy)}<Text style={{color:"#52665e",fontSize:12}}>The PDF includes only this saved assessment. {Platform.OS==="web"?"Choose Save as PDF in the print dialog.":"Choose a folder when prompted. No file is sent automatically."}</Text></View>:null}</View>;
}
