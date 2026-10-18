import React from "react";
import {Pressable,StyleSheet,Text,TextInput,View} from "react-native";
import {AssessmentSymptoms} from "@smart-skin/shared";

export const emptySymptoms=():AssessmentSymptoms=>({body_area:"",onset:"",itching:"not_sure",pain:"not_sure",description:""});
export default function SymptomsForm({value,onChange,disabled}:{value:AssessmentSymptoms;onChange:(value:AssessmentSymptoms)=>void;disabled:boolean}){
  return <View style={styles.box}><Text style={styles.heading}>Symptom details</Text><Text style={styles.body}>Patient-reported context for doctor review. These details are not used by the image-only AI model. Use fictional details for this demo.</Text>
    <Text style={styles.label}>Body area *</Text><TextInput accessibilityLabel="Body area" value={value.body_area} onChangeText={body_area=>onChange({...value,body_area})} editable={!disabled} maxLength={80} placeholder="e.g. forearm, face, or not sure" style={styles.input}/>
    <Text style={styles.label}>When did it start? *</Text><TextInput accessibilityLabel="Symptom onset" value={value.onset} onChangeText={onset=>onChange({...value,onset})} editable={!disabled} maxLength={100} placeholder="e.g. 3 days ago, or not sure / no concern" style={styles.input}/>
    {([['itching','Itching'],['pain','Pain']] as const).map(([key,label])=><View key={key}><Text style={styles.label}>{label}</Text><View style={styles.row}>{([['yes','Yes'],['no','No'],['not_sure','Not sure']] as const).map(([choice,text])=><Pressable key={choice} accessibilityRole="button" accessibilityLabel={`${label}: ${text}`} accessibilityState={{selected:value[key]===choice}} disabled={disabled} style={[styles.choice,value[key]===choice&&styles.selected]} onPress={()=>onChange({...value,[key]:choice})}><Text style={styles.body}>{text}</Text></Pressable>)}</View></View>)}
    <Text style={styles.label}>Description (optional)</Text><TextInput accessibilityLabel="Symptom description" value={value.description} onChangeText={description=>onChange({...value,description})} editable={!disabled} maxLength={1000} multiline placeholder="Any other context you want the doctor to know." style={[styles.input,{minHeight:80}]}/>
    <Text style={styles.body}>* Enter a body area and onset, or write “not sure”. Itching and pain are not assumed absent.</Text>
  </View>;
}
const styles=StyleSheet.create({box:{marginVertical:14},heading:{fontSize:17,fontWeight:"600",color:"#19352e"},body:{fontSize:13,lineHeight:20,color:"#52665e"},label:{fontWeight:"600",color:"#19352e",marginTop:12,marginBottom:6},input:{borderWidth:1,borderColor:"#ccdcd4",borderRadius:9,padding:12,color:"#19352e",textAlignVertical:"top"},row:{flexDirection:"row",gap:8,flexWrap:"wrap"},choice:{padding:10,borderWidth:1,borderColor:"#ccdcd4",borderRadius:8},selected:{backgroundColor:"#e7f4ed",borderColor:"#176f5e",borderWidth:2}});
