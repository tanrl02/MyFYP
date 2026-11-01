import type {AssessmentReport} from "./index";

const escape=(value:unknown)=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
export const reportTime=(value:string)=>new Date(value).toLocaleString("en-MY",{timeZone:"Asia/Kuala_Lumpur",year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:true})+" MYT";
export const assessmentReportNotice="Personal health information. This is a saved snapshot. Downloaded or printed copies cannot be withdrawn by revoking a share. Demo identities are simulated; AI suggestions are experimental and do not confirm a diagnosis.";
export const assessmentReportSignature=({generated_at:_,...content}:AssessmentReport)=>JSON.stringify(content);
export const assessmentReportFilename=(report:AssessmentReport)=>`assessment-${report.assessment.id.replace(/[^a-zA-Z0-9-]/g,"").slice(0,40)}-${report.generated_at.replace(/[^0-9]/g,"")}.pdf`;
export function assessmentReportSections(report:AssessmentReport):{title:string;text:string}[]{
 const a=report.assessment,s=a.symptoms,p=a.prediction;
 return [
  {title:"Report details",text:`Patient: ${report.patient_name}\nPatient ID: ${a.patient_id}\nAssessment ID: ${a.id}\nSaved: ${reportTime(a.created_at)}\nGenerated: ${reportTime(report.generated_at)}\nCopy: ${report.scope==="doctor"?"Doctor - current shared assessment only":"Patient - own assessment"}${report.source_share_id?`\nSource share: ${report.source_share_id}`:""}`},
  {title:"Patient-reported symptoms",text:s?`Body area: ${s.body_area}\nOnset: ${s.onset}\nItching: ${s.itching.replace("_"," ")}\nPain: ${s.pain.replace("_"," ")}\nDescription: ${s.description||"Not supplied"}`:"No symptom details were saved for this assessment."},
  {title:a.origin==="experimental_ai"?"Experimental AI results":"Simulation result",text:p?`Analysed: ${reportTime(p.created_at)}\nModel: ${p.model_id}\n${p.top_predictions.map((x,i)=>`${i+1}. ${x.label}: ${(x.score*100).toFixed(1)}%`).join("\n")}\nScores rank model suggestions. They are not diagnostic certainty or a measure of improvement.\n${a.message}`:`${a.example_category||"No AI prediction saved"}\nSimulation example only. This is not a disease prediction.\n${a.message}`},
  ...report.reviews.map(r=>({title:"Published doctor review",text:`${r.doctor_name} - ${reportTime(r.created_at)}${r.access_revoked?"\nHistorical review: patient has revoked this share.":""}\nDoctor's assessment: ${r.doctor_assessment||"Not separately recorded in this older review"}\nNotes: ${r.note}\nFollow-up: ${r.follow_up}`})),
  ...(report.reviews.length?[]:[{title:"Published doctor reviews",text:report.scope==="doctor"?"No published review for this share. Private drafts are excluded.":"No published doctor reviews for this assessment. Private drafts are excluded."}]),
 ];
}
export function assessmentReportHtml(report:AssessmentReport):string {
 const photo=report.assessment.photo_uri;
 const safePhoto=photo&&/^data:image\/jpeg;base64,[A-Za-z0-9+/]+=*$/.test(photo)?photo:null;
 return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Skin assessment report</title><style>
 @page{size:A4;margin:16mm}*{box-sizing:border-box}body{font:10.5pt/1.45 Arial,sans-serif;color:#19352e;margin:0;padding:24px;background:white}h1{font-size:22pt;margin:0 0 5px}h2{font-size:13pt;margin:20px 0 7px;break-after:avoid}p{margin:6px 0;white-space:pre-wrap;overflow-wrap:anywhere;orphans:3;widows:3}.badge{font-weight:bold;color:#385b4b}.notice{padding:12px;background:#eef5f0;border-left:3px solid #32684f;font-size:10pt}.photo{display:block;max-width:100%;width:260px;height:160px;object-fit:contain;margin:12px 0;break-inside:avoid}.foot{margin-top:24px;border-top:1px solid #c7d6ce;padding-top:10px;font-size:9pt;color:#52665e}@media print{body{padding:0}}
 </style></head><body><h1>Skin assessment report</h1><p class="badge">Smart Skin FYP - demo / experimental system</p><p class="notice">${escape(assessmentReportNotice)}</p>${assessmentReportSections(report).map((s,i)=>`<section><h2>${escape(s.title)}</h2><p>${escape(s.text)}</p>${i===0?(safePhoto?`<img class="photo" alt="Saved assessment photo" src="${safePhoto}">`:'<p>Photo unavailable in this report.</p>'):""}</section>`).join("")}<p class="foot">One assessment only. Patient-reported symptoms, model suggestions and the doctor's published opinion are separate sources. This report does not include private drafts, other assessments, prescriptions or appointment records.</p></body></html>`;
}
