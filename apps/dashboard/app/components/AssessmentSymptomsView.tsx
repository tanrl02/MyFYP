import {AssessmentSymptoms} from "@smart-skin/shared";
const answer={yes:"Yes",no:"No",not_sure:"Not sure"};
export default function AssessmentSymptomsView({symptoms}:{symptoms:AssessmentSymptoms|null}){
  return <section className="my-3 rounded-lg bg-slate-50 p-3 text-slate-800"><h3 className="font-semibold">Patient-reported symptoms</h3>{symptoms?<>
    <p className="mt-2 whitespace-pre-wrap">Body area: {symptoms.body_area}</p><p className="whitespace-pre-wrap">Started: {symptoms.onset}</p><p>Itching: {answer[symptoms.itching]} · Pain: {answer[symptoms.pain]}</p>
    {symptoms.description?<p className="mt-2 whitespace-pre-wrap break-words">{symptoms.description}</p>:null}<p className="mt-2 text-xs">For doctor review; not used by the image-only AI model.</p>
  </>:<p className="mt-2">No symptom details were recorded for this assessment.</p>}</section>;
}
