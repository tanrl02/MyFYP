import React from "react";
import {StyleSheet,Text,View} from "react-native";
import {AssessmentSymptoms} from "@smart-skin/shared";

const answer={yes:"Yes",no:"No",not_sure:"Not sure"};
export default function AssessmentSymptomsView({symptoms}:{symptoms:AssessmentSymptoms|null}){
  return <View style={styles.box}><Text style={styles.title}>Patient-reported symptoms</Text>{symptoms?<>
    <Text style={styles.body}>Body area: {symptoms.body_area}</Text><Text style={styles.body}>Started: {symptoms.onset}</Text>
    <Text style={styles.body}>Itching: {answer[symptoms.itching]} · Pain: {answer[symptoms.pain]}</Text>
    {symptoms.description?<Text style={styles.body}>{symptoms.description}</Text>:null}
    <Text style={styles.body}>For doctor review; not used by the image-only AI model.</Text>
  </>:<Text style={styles.body}>No symptom details were recorded for this assessment.</Text>}</View>;
}
const styles=StyleSheet.create({box:{backgroundColor:"#f1f6fa",borderRadius:10,padding:14,marginVertical:12},title:{fontWeight:"600",fontSize:16,color:"#19352e",marginBottom:6},body:{fontSize:13,lineHeight:20,color:"#52665e",marginTop:4}});
