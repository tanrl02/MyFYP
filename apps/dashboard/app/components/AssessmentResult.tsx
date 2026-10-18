import {Assessment} from "@smart-skin/shared";

export default function AssessmentResult({assessment}:{assessment:Assessment}){
  const prediction=assessment.prediction;
  return <div className="my-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
    <strong>{assessment.origin==="experimental_ai"?"AI suggestions · EXPERIMENTAL":"AI result · SIMULATION"}</strong>
    <p className="mt-2">{assessment.message}</p>
    {prediction?<><ol className="my-3 list-decimal pl-5">{prediction.top_predictions.map(item=><li key={item.condition}>{item.label} · {(item.score*100).toFixed(1)}% model score</li>)}</ol>
      <p>Scores rank suggestions; they are not diagnostic certainty. Only eight learned conditions are compared. Review the photo independently.</p>
      <p className="mt-2">Development validation: {(prediction.validation_accuracy*100).toFixed(1)}% accuracy on {prediction.validation_cases} images; independent final testing pending.</p>
      <p className="mt-2 break-words text-xs">Model version: {prediction.model_id}</p></>:<p>{assessment.example_category}</p>}
  </div>;
}
