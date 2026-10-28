import React,{useState} from "react";
import {Pressable,StyleSheet,Text,View} from "react-native";
import {Assessment,getConditionInformation} from "@smart-skin/shared";
import AssessmentSymptomsView from "./AssessmentSymptomsView";
import ConditionInformation from "./ConditionInformation";
export default function AssessmentResult({assessment}:{assessment:Assessment}){return <ResultContent key={assessment.id} assessment={assessment}/>;}
function ResultContent({assessment}:{assessment:Assessment}){
  const [selected,setSelected]=useState<string|null>(null);const prediction=assessment.prediction;
  return <View><AssessmentSymptomsView symptoms={assessment.symptoms}/>{assessment.origin!=="experimental_ai"||!prediction?<><Text style={styles.title}>SIMULATION · {assessment.example_category}</Text><Text style={styles.body}>{assessment.message}</Text></>:<><Text style={styles.title}>AI suggestions · EXPERIMENTAL</Text><Text style={styles.body}>{assessment.message}</Text>
    {prediction.top_predictions.map((item,index)=><View key={item.condition} style={styles.row}>{getConditionInformation(item.condition)?<Pressable accessibilityRole="button" accessibilityLabel={`About ${item.label}`} accessibilityState={{expanded:selected===item.condition}} onPress={()=>setSelected(item.condition)} style={{flex:1}}><Text style={[styles.body,styles.link]}>{index+1}. {item.label} · About</Text></Pressable>:<Text style={[styles.body,{flex:1}]}>{index+1}. {item.label}</Text>}<Text style={styles.score}>{(item.score*100).toFixed(1)}%</Text></View>)}
    <Text style={styles.body}>Model scores rank suggestions; they are not diagnostic certainty. The model only compares eight learned conditions and cannot reliably identify other conditions.</Text><Text style={styles.small}>Development validation: {(prediction.validation_accuracy*100).toFixed(1)}% accuracy on {prediction.validation_cases} images. Independent final testing is pending.</Text><Text style={styles.small}>Model version: {prediction.model_id}</Text></>}
    <ConditionInformation selected={selected} onSelect={setSelected}/>
  </View>;
}
const styles=StyleSheet.create({title:{fontSize:16,fontWeight:"600",color:"#825b16",marginVertical:8},body:{fontSize:13,lineHeight:20,color:"#52665e",marginVertical:4},row:{flexDirection:"row",justifyContent:"space-between",gap:12},score:{fontWeight:"600",color:"#19352e",marginVertical:4},small:{fontSize:12,lineHeight:18,color:"#637970",marginTop:8},link:{color:"#176f5e",textDecorationLine:"underline",paddingVertical:6}});
