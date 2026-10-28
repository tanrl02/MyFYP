"use client";
import {useState} from "react";
import ConditionInformation from "./ConditionInformation";
import {Assessment,getConditionInformation} from "@smart-skin/shared";
import AssessmentSymptomsView from "./AssessmentSymptomsView";

export default function AssessmentResult({assessment}:{assessment:Assessment}){return <ResultContent key={assessment.id} assessment={assessment}/>;}
function ResultContent({assessment}:{assessment:Assessment}){
  const [selected,setSelected]=useState<string|null>(null);
  const prediction=assessment.prediction;
  return <div className="my-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
    <AssessmentSymptomsView symptoms={assessment.symptoms}/><strong>{assessment.origin==="experimental_ai"?"AI suggestions · EXPERIMENTAL":"AI result · SIMULATION"}</strong>
    <p className="mt-2">{assessment.message}</p>
    {prediction?<><ol className="my-3 list-decimal pl-5">{prediction.top_predictions.map(item=><li key={item.condition}>{getConditionInformation(item.condition)?<button className="underline" aria-label={`About ${item.label}`} aria-expanded={selected===item.condition} onClick={()=>setSelected(item.condition)}>{item.label} · About</button>:item.label} · {(item.score*100).toFixed(1)}% model score</li>)}</ol>
      <p>Scores rank suggestions; they are not diagnostic certainty. Only eight learned conditions are compared. Review the photo independently.</p>
      <p className="mt-2">Development validation: {(prediction.validation_accuracy*100).toFixed(1)}% accuracy on {prediction.validation_cases} images; independent final testing pending.</p>
      <p className="mt-2 break-words text-xs">Model version: {prediction.model_id}</p></>:<p>{assessment.example_category}</p>}
    <ConditionInformation selected={selected} onSelect={setSelected}/>
  </div>;
}
