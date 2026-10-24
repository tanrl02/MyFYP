import React,{useState} from "react";
import {Pressable,StyleSheet,Text,View} from "react-native";

const clinicToday=()=>new Date(Date.now()+8*3600000).toISOString().slice(0,10);
const monthName=(month:string)=>new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-GB",{month:"long",year:"numeric",timeZone:"UTC"});
export const bookingDateLabel=(date:string)=>new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"});

export default function BookingDateFilter({value,onChange,busy,allowPast=false,title="Visit date"}:{value:string|null;onChange:(date:string|null)=>void;busy:boolean;allowPast?:boolean;title?:string}){
  const today=clinicToday();
  const [open,setOpen]=useState(false),[month,setMonth]=useState(()=>(value||today).slice(0,7));
  const first=new Date(`${month}-01T00:00:00Z`),offset=(first.getUTCDay()+6)%7;
  const count=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
  function move(amount:number){setMonth(new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+amount,1)).toISOString().slice(0,7));}
  return <View style={styles.card}>
    <Text style={styles.heading}>{title}</Text>
    <Text accessibilityLiveRegion="polite" style={styles.muted}>{value?`Showing ${bookingDateLabel(value)} (Malaysia time)`:'Showing all dates (Malaysia time)'}</Text>
    <View style={styles.row}>
      <Pressable accessibilityRole="button" accessibilityState={{selected:value===null}} disabled={busy} style={[styles.choice,value===null&&styles.active]} onPress={()=>{onChange(null);setOpen(false);}}><Text style={styles.link}>Show all dates</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityState={{expanded:open}} disabled={busy} style={styles.choice} onPress={()=>{if(!open)setMonth((value||today).slice(0,7));setOpen(!open);}}><Text style={styles.link}>{open?'Close calendar':'Choose a date'}</Text></Pressable>
    </View>
    {open?<View style={styles.calendar}>
      <View style={styles.navigation}>
        <Pressable accessibilityRole="button" accessibilityLabel={allowPast?"Previous visit month":"Previous booking month"} disabled={busy||(!allowPast&&month<=today.slice(0,7))} style={[styles.navigationButton,(busy||(!allowPast&&month<=today.slice(0,7)))&&styles.disabled]} onPress={()=>move(-1)}><Text style={styles.link}>Previous</Text></Pressable>
        <Text style={styles.month}>{monthName(month)}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel={allowPast?"Next visit month":"Next booking month"} disabled={busy} style={styles.navigationButton} onPress={()=>move(1)}><Text style={styles.link}>Next</Text></Pressable>
      </View>
      <View style={styles.grid}>{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day=><View key={day} style={styles.cell}><Text style={styles.weekday}>{day}</Text></View>)}</View>
      <View style={styles.grid}>{Array.from({length:Math.ceil((offset+count)/7)*7},(_,index)=>{
        const number=index-offset+1;
        if(number<1||number>count)return <View key={index} style={styles.cell}/>;
        const date=`${month}-${String(number).padStart(2,'0')}`,past=!allowPast&&date<today;
        return <View key={index} style={styles.cell}><Pressable accessibilityRole="button" accessibilityLabel={`Choose ${bookingDateLabel(date)}`} accessibilityState={{selected:value===date}} disabled={busy||past} style={[styles.day,value===date&&styles.active,(busy||past)&&styles.disabled]} onPress={()=>{onChange(date);setOpen(false);}}><Text style={styles.link}>{number}</Text></Pressable></View>;
      })}</View>
      <Text style={styles.muted}>{allowPast?'Choose a past or future appointment date to filter your saved visits.':'Choose today or a future date. Appointment times depend on the clinic schedule.'}</Text>
    </View>:null}
  </View>;
}
const styles=StyleSheet.create({card:{padding:16,borderWidth:1,borderColor:'#dce6e0',backgroundColor:'white',borderRadius:14,marginBottom:18},heading:{fontSize:18,fontWeight:'600',color:'#19352e',marginBottom:8},muted:{fontSize:13,lineHeight:20,color:'#637970',marginBottom:8},row:{flexDirection:'row',flexWrap:'wrap',gap:10},choice:{paddingHorizontal:12,paddingVertical:4,borderRadius:10,borderWidth:1,borderColor:'#dce6e0'},active:{borderColor:'#176f5e',backgroundColor:'#e7f4ed',borderWidth:2},link:{color:'#176f5e',fontWeight:'600',paddingVertical:8},calendar:{marginTop:14,maxWidth:420,width:'100%',alignSelf:'center'},navigation:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:4,marginBottom:10},navigationButton:{paddingHorizontal:4,minHeight:44,justifyContent:'center'},month:{fontWeight:'600',color:'#19352e',flexShrink:1,textAlign:'center'},grid:{flexDirection:'row',flexWrap:'wrap'},cell:{width:'14.285714%',alignItems:'center',justifyContent:'center',minHeight:44},day:{width:'100%',minHeight:44,alignItems:'center',justifyContent:'center',borderRadius:8,borderWidth:1,borderColor:'transparent'},weekday:{fontSize:12,color:'#637970'},disabled:{opacity:.35}});
