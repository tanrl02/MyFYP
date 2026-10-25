import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, AppState, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { DemoApi, NotificationInbox, PatientNotification, visitTime } from "@smart-skin/shared";
import { filterNotifications, NotificationFilter, NotificationType, notificationFilterLabels, notificationTypeLabels } from "./patientNotificationFilter";
export default function NotificationsView({api,isActive,onOpen,onBusy,status,setStatus,type,setType,query,setQuery,onUnreadCount}:{api:DemoApi;isActive:boolean;onOpen:(item:PatientNotification)=>void;onBusy:(value:boolean)=>void;status:NotificationFilter;setStatus:(value:NotificationFilter)=>void;type:NotificationType;setType:(value:NotificationType)=>void;query:string;setQuery:(value:string)=>void;onUnreadCount:(value:number|null)=>void}){
  const [data,setData]=useState<NotificationInbox|null>(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [retry,setRetry]=useState(0);
  const [review,setReview]=useState<string[]|null>(null),[notice,setNotice]=useState("");
  const saving=useRef(false),loadVersion=useRef(0),history=useRef(false);
  const [browsingOlder,setBrowsingOlder]=useState(false),[olderError,setOlderError]=useState("");
  useEffect(()=>{setReview(null);setNotice("");},[query,status,type]);
  useEffect(()=>{if(!isActive){setReview(null);setNotice("");}},[isActive]);
  const visible=filterNotifications(data?.items||[],status,type,query);
  const unreadDisplayed=visible.filter(item=>!item.read_at);
  useEffect(()=>{if(data)onUnreadCount(data.unread_count);else if(error)onUnreadCount(null);},[data,error,onUnreadCount]);
  useEffect(()=>{if(!isActive)return;let active=true,fetching=false;async function load(){if(fetching||saving.current||history.current)return;fetching=true;const version=loadVersion.current;try{const saved=await api.notifications();if(active&&version===loadVersion.current){setData(saved);setError("");}}catch(e){if(active&&version===loadVersion.current){setData(null);setError(e instanceof Error?e.message:"Cannot load notifications.");}}finally{fetching=false;if(active)setLoading(false);}}void load();const timer=setInterval(load,5000),subscription=AppState.addEventListener("change",state=>{if(state==="active")void load();});return()=>{active=false;clearInterval(timer);subscription.remove();};},[api,retry,isActive]);
  async function read(item:PatientNotification,open:boolean){if(saving.current)return;saving.current=true;loadVersion.current++;setReview(null);setNotice("");setBusy(true);onBusy(true);setError("");try{const saved=await api.readNotification(item.id);loadVersion.current++;setData(current=>current?{...current,items:current.items.map(n=>n.id===saved.id?saved:n),unread_count:Math.max(0,current.unread_count-(current.items.some(n=>n.id===saved.id&&!n.read_at)?1:0))}:null);setRetry(r=>r+1);if(open)onOpen(item);}catch(e){setError(e instanceof Error?e.message:"Cannot mark notification as read.");}finally{saving.current=false;setBusy(false);onBusy(false);}}
  async function unread(item:PatientNotification){
    if(saving.current)return;
    saving.current=true;loadVersion.current++;setReview(null);setNotice("");setBusy(true);onBusy(true);setError("");
    try{
      const result=await api.unreadNotification(item.id);loadVersion.current++;
      setData(current=>current?{...current,items:current.items.map(n=>n.id===result.item.id?result.item:n),unread_count:result.unread_count}:null);
      onUnreadCount(result.unread_count);setNotice("Message marked as unread.");setRetry(value=>value+1);
    }catch(e){setError(e instanceof Error?e.message:"Cannot mark notification as unread.");}
    finally{saving.current=false;setBusy(false);onBusy(false);}
  }
  async function readDisplayed(){
    if(saving.current||!review?.length||!data||error)return;
    const ids=[...review];saving.current=true;loadVersion.current++;setBusy(true);onBusy(true);setError("");setNotice("");
    try{
      const result=await api.readDisplayedNotifications(ids);loadVersion.current++;
      const saved=new Map(result.items.map(item=>[item.id,item]));
      setData(current=>current?{...current,items:current.items.map(item=>saved.get(item.id)||item),unread_count:result.unread_count}:null);
      onUnreadCount(result.unread_count);setReview(null);
      setNotice(`${result.marked_count} message${result.marked_count===1?"":"s"} marked as read. Already-read messages were left unchanged.`);
      setRetry(value=>value+1);
    }catch(e){setReview(null);setError(e instanceof Error?e.message:"Unable to mark displayed messages as read. Refresh and review again.");}
    finally{saving.current=false;setBusy(false);onBusy(false);}
  }
  function refreshNewest(){
    if(saving.current)return;
    history.current=false;setBrowsingOlder(false);loadVersion.current++;
    setReview(null);setNotice("");setOlderError("");setLoading(true);setRetry(value=>value+1);
  }
  async function loadOlder(){
    if(saving.current||!data?.next_cursor)return;
    const cursor=data.next_cursor;
    history.current=true;setBrowsingOlder(true);saving.current=true;loadVersion.current++;
    setBusy(true);onBusy(true);setReview(null);setNotice("");setOlderError("");
    try{
      const page=await api.notifications(cursor);
      setData(current=>current?{...page,items:[...current.items,...page.items.filter(item=>!current.items.some(existing=>existing.id===item.id))]}:null);
      setError("");
    }catch(e){setOlderError(e instanceof Error?e.message:"Cannot load older notifications. Try again.");}
    finally{saving.current=false;setBusy(false);onBusy(false);}
  }
  return <View><Text style={s.title}>Notifications</Text><Text style={s.body}>Upcoming appointment reminders, queue calls, published doctor reviews, follow-up recommendations, issued or cancelled prescriptions, newly generated bills and recorded simulated payments appear here. Open a record to check its latest details. Opening a notification marks it as read.</Text><Text style={s.body}>While the app is open, notification refreshes check for waiting visits in the next 24 hours. Cancelled, rescheduled, called, completed and past reminders disappear. In-app only; no phone push alerts.</Text>{loading?<ActivityIndicator color="#176f5e"/>:null}{error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}<Pressable accessibilityRole="button" disabled={busy} onPress={refreshNewest}><Text style={s.link}>{browsingOlder?"Refresh newest notifications":"Refresh notifications"}</Text></Pressable><Text style={s.heading}>Search notifications</Text><TextInput accessibilityLabel="Search notification titles and messages" placeholder="Search title or message, e.g. L001" value={query} onChangeText={setQuery} editable={!busy} autoCapitalize="none" autoCorrect={false} maxLength={100} style={s.input}/><Text style={s.heading}>Read status</Text><View accessibilityRole="radiogroup" accessibilityLabel="Notification read status" style={s.filters}>{(Object.keys(notificationFilterLabels) as NotificationFilter[]).map(key=><Pressable key={key} accessibilityRole="radio" aria-checked={status===key} accessibilityState={{checked:status===key,disabled:busy}} disabled={busy} onPress={()=>setStatus(key)} style={[s.choice,status===key&&s.active,busy&&{opacity:.45}]}><Text style={s.link}>{notificationFilterLabels[key]}</Text></Pressable>)}</View><Text style={s.heading}>Notification type</Text><View accessibilityRole="radiogroup" accessibilityLabel="Notification type" style={s.filters}>{(Object.keys(notificationTypeLabels) as NotificationType[]).map(key=><Pressable key={key} accessibilityRole="radio" aria-checked={type===key} accessibilityState={{checked:type===key,disabled:busy}} disabled={busy} onPress={()=>setType(key)} style={[s.choice,type===key&&s.active,busy&&{opacity:.45}]}><Text style={s.link}>{notificationTypeLabels[key]}</Text></Pressable>)}</View><Pressable accessibilityRole="button" disabled={busy||(!query&&status==="all"&&type==="all")} style={(busy||(!query&&status==="all"&&type==="all"))&&{opacity:.45}} onPress={()=>{if(busy)return;setQuery("");setStatus("all");setType("all");}}><Text style={s.link}>Reset notification filters</Text></Pressable><View style={s.batch}>
    {notice?<Text accessibilityLiveRegion="polite" style={s.body}>{notice}</Text>:null}
    {review?<>
      <Text style={s.heading}>Mark {review.length} reviewed unread message{review.length===1?"":"s"} as read?</Text>
      <Text style={s.body}>Only the messages included when you started this review will be updated. New arrivals are excluded, and messages already read stay unchanged.</Text>
      <Pressable accessibilityRole="button" disabled={busy||!data||!!error} onPress={readDisplayed}><Text style={s.link}>{busy?"Saving…":"Confirm mark as read"}</Text></Pressable>
      <Pressable accessibilityRole="button" disabled={busy} onPress={()=>setReview(null)}><Text style={s.link}>Keep messages unread</Text></Pressable>
    </>:<Pressable accessibilityRole="button" disabled={busy||loading||!!error||!unreadDisplayed.length} style={(busy||loading||!!error||!unreadDisplayed.length)&&{opacity:.45}} onPress={()=>{setNotice("");setReview(unreadDisplayed.slice(0,100).map(item=>item.id));}}><Text style={s.link}>Mark displayed messages as read</Text></Pressable>}
  </View><Text style={s.body}>Filters apply to all loaded notifications. Load older messages to search earlier entries. Filtering does not mark messages as read. Each read review includes up to 100 displayed unread messages.</Text>{data?<><Text style={s.count}>{data.unread_count} unread across all notifications</Text><Text style={s.body}>Showing {visible.length} of {data.items.length} loaded notifications</Text>
    {browsingOlder?<Text style={s.body}>Automatic refresh is paused while browsing older messages. Refresh newest notifications to return to the latest 100 and resume updates.</Text>:null}
    {olderError?<Text accessibilityRole="alert" style={s.error}>{olderError}</Text>:null}
    {data.next_cursor?<Pressable accessibilityRole="button" disabled={busy||loading} onPress={loadOlder}><Text style={s.link}>{busy?"Please wait…":olderError?"Retry older notifications":"Load older notifications"}</Text></Pressable>:<Text style={s.body}>All available notifications loaded.</Text>}{visible.map(item=><View key={item.id} style={s.card}><Text style={s.badge}>{item.read_at?"Read":"Unread"}</Text><Text style={s.heading}>{item.title}</Text><Text style={s.body}>{item.message}</Text><Text style={s.time}>{visitTime(item.created_at)}</Text><Pressable accessibilityRole="button" accessibilityLabel={`Open notification ${item.id.slice(0,8)}`} disabled={busy} onPress={()=>read(item,true)}><Text style={s.link}>{(item.kind==="prescription_issued"||item.kind==="prescription_cancelled")?"Open prescription →":item.kind==="payment_recorded"?"Open bill & receipt →":item.kind==="bill_ready"?"Open bill →":item.kind!=="review_published"?"Open visit →":"Open assessment & review →"}</Text></Pressable>{!item.read_at?<Pressable accessibilityRole="button" accessibilityLabel={`Mark notification ${item.id.slice(0,8)} as read`} disabled={busy} onPress={()=>read(item,false)}><Text style={s.link}>Mark as read</Text></Pressable>:<Pressable accessibilityRole="button" accessibilityLabel={`Mark notification ${item.id.slice(0,8)} as unread`} disabled={busy} onPress={()=>unread(item)}><Text style={s.link}>Mark as unread</Text></Pressable>}</View>)}{!data.items.length?<View style={s.card}><Text style={s.heading}>No notifications yet</Text><Text style={s.body}>Upcoming visits within 24 hours, new queue calls, published reviews, follow-up recommendations, issued or cancelled prescriptions, newly generated bills and recorded simulated payments will appear here.</Text></View>:!visible.length?<View style={s.card}><Text style={s.heading}>No matching notifications in the loaded list</Text><Text style={s.body}>Change the search, read status or notification type to see other loaded messages. Use Reset notification filters to restore the full loaded list.</Text></View>:null}</>:null}</View>;
}
const s=StyleSheet.create({batch:{padding:14,borderWidth:1,borderColor:"#dce6e0",borderRadius:12,backgroundColor:"#edf5f0",marginVertical:10},input:{padding:12,borderWidth:1,borderColor:"#ccdcd4",borderRadius:10,color:"#19352e",backgroundColor:"white",marginTop:10,marginBottom:8},filters:{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:8},choice:{paddingHorizontal:16,borderRadius:10,borderWidth:1,borderColor:"#dce6e0",backgroundColor:"#e7efeb"},active:{borderWidth:2,borderColor:"#176f5e"},title:{fontSize:23,fontWeight:"700",color:"#19352e",marginBottom:8},heading:{fontSize:16,fontWeight:"600",color:"#19352e",marginTop:8},body:{fontSize:13,lineHeight:21,color:"#637970",marginVertical:8},count:{fontSize:13,fontWeight:"600",color:"#19352e",marginVertical:12},card:{padding:20,backgroundColor:"#fff",borderWidth:1,borderColor:"#dce6e0",borderRadius:16,marginBottom:14},badge:{fontSize:12,fontWeight:"600",color:"#176f5e"},time:{fontSize:12,color:"#637970",marginTop:4},link:{fontSize:13,fontWeight:"600",color:"#176f5e",paddingVertical:12},error:{backgroundColor:"#fff0f0",padding:14,color:"#9f2929",borderRadius:12}});
