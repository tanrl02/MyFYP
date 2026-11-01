"use client";
import {useEffect,useRef,useState} from "react";
import {AssessmentReport,DemoApi,assessmentReportHtml,assessmentReportSignature,assessmentReportNotice} from "@smart-skin/shared";

export default function AssessmentReportPreview({api,shareId}:{api:DemoApi;shareId:string}){
 const [report,setReport]=useState<AssessmentReport|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const frame=useRef<HTMLIFrameElement>(null),active=useRef(true),[ready,setReady]=useState(false);
 useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
 async function preview(){setBusy(true);setMessage("");setReady(false);try{const data=await api.sharedAssessmentReport(shareId);if(active.current)setReport(data);}catch(e){if(active.current){setReport(null);setMessage(e instanceof Error?e.message:"Report unavailable.");}}finally{if(active.current)setBusy(false);}}
 async function print(){if(!report||busy||!ready)return;setBusy(true);setMessage("");try{
  const fresh=await api.sharedAssessmentReport(shareId);if(!active.current)return;
  if(assessmentReportSignature(fresh)!==assessmentReportSignature(report)){setReady(false);setReport(fresh);setMessage("Report changed. Review the updated preview before exporting.");return;}
  if(!frame.current?.contentWindow)throw new Error("Preview unavailable. Reopen the report.");
  frame.current.contentWindow.focus();frame.current.contentWindow.print();
 }catch(e){if(active.current){setReport(null);setMessage(e instanceof Error?e.message:"Cannot print report.");}}finally{if(active.current)setBusy(false);}}
 return <div className="my-4 border-t border-[#dce6e0] pt-4"><button className="btn secondary" disabled={busy} onClick={preview}>{busy?"Checking report…":report?"Refresh report preview":"Preview assessment report"}</button>{message?<p role="status" className="my-3">{message}</p>:null}{report?<><p className="my-3 text-sm">{assessmentReportNotice}</p><iframe ref={frame} title="Assessment report preview" sandbox="allow-same-origin allow-modals" srcDoc={assessmentReportHtml(report)} onLoad={()=>setReady(true)} className="h-[600px] w-full border border-[#ccdcd4]"/><div className="my-3 flex gap-3"><button className="btn" disabled={busy||!ready} onClick={print}>Print / Save PDF</button><button className="btn secondary" disabled={busy} onClick={()=>{setReport(null);setMessage("");}}>Close report</button></div><p className="muted text-xs">Only this report opens in the print dialog. Choose Save as PDF for a file. Access is checked again before opening the dialog.</p></>:null}</div>;
}
