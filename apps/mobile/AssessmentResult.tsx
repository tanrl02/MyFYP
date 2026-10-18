import React from "react";
import {StyleSheet,Text,View} from "react-native";
import {Assessment} from "@smart-skin/shared";
import AssessmentSymptomsView from "./AssessmentSymptomsView";

export default function AssessmentResult({assessment}:{assessment:Assessment}){
  const prediction=assessment.prediction;
  if(assessment.origin!=="experimental_ai"||!prediction)return <View><AssessmentSymptomsView symptoms={assessment.symptoms}/><Text style={styles.title}>SIMULATION · {assessment.example_category}</Text><Text style={styles.body}>{assessment.message}</Text></View>;
  return <View><AssessmentSymptomsView symptoms={assessment.symptoms}/><Text style={styles.title}>AI suggestions · EXPERIMENTAL</Text><Text style={styles.body}>{assessment.message}</Text>
    {prediction.top_predictions.map((item,index)=><View key={item.condition} style={styles.row}><Text style={styles.body}>{index+1}. {item.label}</Text><Text style={styles.score}>{(item.score*100).toFixed(1)}%</Text></View>)}
    <Text style={styles.body}>Model scores rank suggestions; they are not diagnostic certainty. The model only compares eight learned conditions and cannot reliably identify other conditions.</Text>
    <Text style={styles.small}>Development validation: {(prediction.validation_accuracy*100).toFixed(1)}% accuracy on {prediction.validation_cases} images. Independent final testing is pending.</Text>
    <Text style={styles.small}>Model version: {prediction.model_id}</Text>
  </View>;
}
const styles=StyleSheet.create({title:{fontSize:16,fontWeight:"600",color:"#825b16",marginVertical:8},body:{fontSize:13,lineHeight:20,color:"#52665e",marginVertical:4},row:{flexDirection:"row",justifyContent:"space-between",gap:12},score:{fontWeight:"600",color:"#19352e",marginVertical:4},small:{fontSize:12,lineHeight:18,color:"#637970",marginTop:8}});
