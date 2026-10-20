import React from "react";
import {Pressable,StyleSheet,Text,View} from "react-native";
import type {Slot} from "@smart-skin/shared";

export type BookingTimePreference="any"|"before_noon"|"from_noon";
export const bookingTimeLabels:Record<BookingTimePreference,string>={any:"Any time",before_noon:"Before 12 pm",from_noon:"12 pm onwards"};
export function matchesBookingTime(slot:Pick<Slot,"starts_at">,preference:BookingTimePreference){
  if(preference==="any")return true;
  // Malaysia stays at UTC+8; never use the phone/browser's local timezone.
  const hour=new Date(Date.parse(slot.starts_at)+8*3600000).getUTCHours();
  return preference==="before_noon"?hour<12:hour>=12;
}
export default function BookingTimeFilter({value,onChange,busy}:{value:BookingTimePreference;onChange:(value:BookingTimePreference)=>void;busy:boolean}){
  return <View style={styles.card}><Text style={styles.heading}>Time preference</Text><Text style={styles.muted}>Based on the appointment start time in Malaysia time.</Text><View accessibilityRole="radiogroup" accessibilityLabel="Time preference" style={styles.row}>{(Object.keys(bookingTimeLabels) as BookingTimePreference[]).map(key=><Pressable key={key} accessibilityRole="radio" aria-checked={value===key} accessibilityState={{checked:value===key}} disabled={busy} style={[styles.choice,value===key&&styles.active]} onPress={()=>onChange(key)}><Text style={styles.link}>{bookingTimeLabels[key]}</Text></Pressable>)}</View></View>;
}
const styles=StyleSheet.create({card:{padding:18,borderWidth:1,borderColor:"#dce6e0",borderRadius:14,backgroundColor:"white",marginBottom:16},heading:{fontSize:18,fontWeight:"600",color:"#19352e",marginBottom:8},muted:{fontSize:13,lineHeight:20,color:"#637970",marginBottom:10},row:{flexDirection:"row",flexWrap:"wrap",gap:8},choice:{padding:10,borderRadius:10,borderWidth:1,borderColor:"#dce6e0",backgroundColor:"#e7efeb"},active:{borderWidth:2,borderColor:"#176f5e"},link:{color:"#176f5e",fontWeight:"600",paddingVertical:8}});
