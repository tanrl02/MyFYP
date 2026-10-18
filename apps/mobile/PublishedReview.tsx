import React from "react";
import {StyleSheet,Text,View} from "react-native";
import {AssessmentReview,visitTime} from "@smart-skin/shared";

export default function PublishedReview({review}:{review:AssessmentReview}){
  return <View style={styles.box}><Text style={styles.title}>Doctor’s assessment · published</Text>
    <Text style={styles.body}>{review.doctor_assessment||"No separate assessment was recorded in this older review. Read the doctor's notes below."}</Text>
    <Text style={styles.body}>Written by the reviewing doctor, separately from the experimental AI ranking.</Text>
    <Text style={styles.label}>Doctor’s notes</Text><Text style={styles.body}>{review.note}</Text>
    <Text style={styles.label}>Follow-up</Text><Text style={styles.body}>{review.follow_up}</Text>
    <Text style={styles.body}>Published {visitTime(review.created_at)}</Text>
  </View>;
}
const styles=StyleSheet.create({box:{backgroundColor:"#e7f4ed",borderRadius:12,padding:14,marginVertical:12},title:{fontSize:16,fontWeight:"700",color:"#19352e",marginBottom:8},label:{fontWeight:"600",color:"#19352e",marginTop:12},body:{fontSize:13,lineHeight:20,color:"#52665e",marginTop:5}});
