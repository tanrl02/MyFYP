import React from "react";
import {Pressable,StyleSheet,Text,TextInput,View} from "react-native";
import {VisitFilter,visitFilterLabels,VisitOrder,visitOrderLabels} from "./patientVisitFilter";
import BookingDateFilter from "./BookingDateFilter";

export default function VisitFilters({query,status,date,order,busy,onQuery,onStatus,onDate,onOrder,onReset}:{query:string;status:VisitFilter;date:string|null;order:VisitOrder;busy:boolean;onQuery:(value:string)=>void;onStatus:(value:VisitFilter)=>void;onDate:(value:string|null)=>void;onOrder:(value:VisitOrder)=>void;onReset:()=>void}){
  return <View style={styles.card}><Text style={styles.heading}>Find a visit</Text>
    <Text style={styles.muted}>Search your appointment cards by doctor or queue number.</Text>
    <TextInput accessibilityLabel="Search my visits by doctor or queue number" placeholder="Doctor or queue number, e.g. L001" value={query} onChangeText={onQuery} editable={!busy} autoCapitalize="none" autoCorrect={false} maxLength={100} style={styles.input}/>
    <BookingDateFilter key={date||"all"} value={date} onChange={onDate} busy={busy} allowPast title="Appointment date"/>
    <View accessibilityRole="radiogroup" accessibilityLabel="Visit status" style={styles.row}>{(Object.keys(visitFilterLabels) as VisitFilter[]).map(key=><Pressable key={key} accessibilityRole="radio" aria-checked={status===key} accessibilityState={{checked:status===key}} disabled={busy} onPress={()=>onStatus(key)} style={[styles.choice,status===key&&styles.active]}><Text style={styles.link}>{visitFilterLabels[key]}</Text></Pressable>)}</View>
    {status==="upcoming"?<Text style={styles.muted}>Upcoming shows Waiting or Called visits scheduled for now or later. Find earlier visits under All visits.</Text>:null}
    <Text style={styles.heading}>Visit order</Text>
    <View accessibilityRole="radiogroup" accessibilityLabel="Visit order" style={styles.row}>{(Object.keys(visitOrderLabels) as VisitOrder[]).map(key=><Pressable key={key} accessibilityRole="radio" aria-checked={order===key} accessibilityState={{checked:order===key}} disabled={busy} onPress={()=>onOrder(key)} style={[styles.choice,order===key&&styles.active]}><Text style={styles.link}>{visitOrderLabels[key]}</Text></Pressable>)}</View>
    <Text style={styles.muted}>Sorted by appointment time. Reset visit filters keeps your chosen order.</Text>
    <Pressable accessibilityRole="button" disabled={busy||(!query&&status==="all"&&!date)} onPress={onReset} style={[styles.reset,(busy||(!query&&status==="all"&&!date))&&{opacity:.45}]}><Text style={styles.link}>Reset visit filters</Text></Pressable>
  </View>;
}
const styles=StyleSheet.create({card:{padding:18,borderWidth:1,borderColor:"#dce6e0",borderRadius:14,backgroundColor:"white",marginBottom:16},heading:{fontSize:18,fontWeight:"600",color:"#19352e",marginBottom:8},muted:{fontSize:13,lineHeight:20,color:"#637970",marginBottom:10},input:{padding:12,borderWidth:1,borderColor:"#ccdcd4",borderRadius:10,color:"#19352e",marginBottom:12},row:{flexDirection:"row",flexWrap:"wrap",gap:8,marginBottom:10},choice:{padding:10,borderRadius:10,borderWidth:1,borderColor:"#dce6e0",backgroundColor:"#e7efeb"},active:{borderWidth:2,borderColor:"#176f5e"},link:{color:"#176f5e",fontWeight:"600"},reset:{paddingVertical:10,alignSelf:"flex-start"}});
