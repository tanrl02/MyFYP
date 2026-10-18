import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { AssessmentShare, Booking, DemoApi, DemoDoctor, DemoPatient, doctorNames, queueToken, visitTime } from "@smart-skin/shared";
import PublishedReview from "./PublishedReview";
import { apiBase } from "./apiConfig";

const requestKey = () => `share-${Date.now()}-${Math.random().toString(36).slice(2)}`;
export default function SharingView({ patient, assessmentId }: { patient: DemoPatient; assessmentId: string }) {
  const api = useMemo(() => new DemoApi(apiBase, patient), [patient]);
  const [shares, setShares] = useState<AssessmentShare[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [mode, setMode] = useState<"doctor" | "appointment">("doctor"), [bookingId, setBookingId] = useState("");
  const [doctor, setDoctor] = useState<DemoDoctor>("doctor-lim");
  const [message, setMessage] = useState("");
  const [request, setRequest] = useState(requestKey);
  const [confirm, setConfirm] = useState(false), [revoke, setRevoke] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true, fetching = false;
    async function load() {
      if (fetching) return; fetching = true;
      try { const [data, visits] = await Promise.all([api.shares(),api.bookings()]); if (active) { setShares(data.filter(s => s.assessment_id === assessmentId)); setBookings(visits); } }
      catch (e) { if (active) setError(e instanceof Error ? e.message : "Cannot load sharing history."); }
      finally { fetching = false; }
    }
    void load(); const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [api, assessmentId]);
  async function act(action: () => Promise<AssessmentShare>, success: string) {
    if (busy) return; setBusy(true); setError(""); setNotice("");
    try {
      const saved = await action();
      setShares(current => [saved, ...current.filter(s => s.id !== saved.id)]);
      setConfirm(false); setRevoke(""); setRequest(requestKey()); setNotice(success);
    } catch (e) { setError(e instanceof Error ? e.message : "Cannot save. Refresh before retrying."); }
    finally { setBusy(false); }
  }
  const alreadyShared = shares.some(s => s.doctor_id === doctor && !s.booking_id && !s.revoked_at);
  const eligible = bookings.filter(b => b.status === "called" || (b.status === "waiting" && new Date(b.starts_at).getTime() > Date.now()));
  const selectedVisit = eligible.find(b => b.id === bookingId);
  const linked = shares.some(s => s.booking_id === bookingId && !s.revoked_at);
  return <View style={styles.box}>
    <Text style={styles.title}>Doctor sharing & review</Text>
    <Text style={styles.body}>Choose who can open this photo, its saved result and your message. Other assessments stay private. Demo accounts only.</Text>
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    {notice ? <Text style={styles.body}>{notice}</Text> : null}
    <View style={styles.row}>{(["doctor","appointment"] as const).map(value => <Pressable accessibilityRole="button" key={value} disabled={busy || confirm} style={[styles.choice,mode===value&&styles.selected]} onPress={() => { setMode(value); setRequest(requestKey()); setNotice(""); }}><Text style={{color:mode===value?"white":"#176f5e"}}>{value==="doctor"?"Share with doctor":"Link to appointment"}</Text></Pressable>)}</View>
    {mode === "doctor" ? <><Text style={styles.label}>Choose a doctor</Text>
    <View style={styles.row}>{(Object.keys(doctorNames) as DemoDoctor[]).map(id => <Pressable accessibilityRole="button" key={id} disabled={busy || confirm} style={[styles.choice, doctor === id && styles.selected]} onPress={() => { setDoctor(id); setRequest(requestKey()); setNotice(""); }}><Text style={{ color: doctor === id ? "white" : "#176f5e" }}>{doctorNames[id]}</Text></Pressable>)}</View>
    </> : <><Text style={styles.label}>Choose an existing appointment</Text><Text style={styles.body}>One assessment per appointment. Only its assigned doctor receives this access. Cancelling the appointment revokes its link.</Text>{eligible.map(visit => <Pressable accessibilityRole="button" accessibilityLabel={`Choose appointment ${queueToken(visit)} ${visit.doctor_name} ${visitTime(visit.starts_at)}`} key={visit.id} disabled={busy || confirm} style={[styles.choice,{marginVertical:5},bookingId===visit.id&&styles.selected]} onPress={() => { setBookingId(visit.id); setRequest(requestKey()); }}><Text style={{color:bookingId===visit.id?"white":"#176f5e"}}>{queueToken(visit)} · {visit.doctor_name} · {visitTime(visit.starts_at)} · {visit.status}</Text></Pressable>)}{!eligible.length ? <Text style={styles.body}>No eligible appointments. Book a visit first; completed and cancelled visits cannot receive new links.</Text> : null}</>}
    <Text style={styles.label}>Message to doctor (optional)</Text>
    <TextInput accessibilityLabel="Message to doctor" multiline maxLength={1000} editable={!busy && !confirm} value={message} onChangeText={text => { setMessage(text); setRequest(requestKey()); }} placeholder="Use fictional symptoms for this demo." style={styles.input} />
    {confirm ? <View>
      <Text style={styles.body}>{mode === "appointment" ? `Link this assessment to ${selectedVisit ? queueToken(selectedVisit) + " · " + selectedVisit.doctor_name + " · " + visitTime(selectedVisit.starts_at) : "the selected appointment"}?` : `Share this assessment with ${doctorNames[doctor]}?`} They can view the photo and publish a review for you. You can revoke future access. Published reviews remain in your history; previously viewed information cannot be recalled.</Text>
      <Pressable accessibilityRole="button" disabled={busy || (mode === "appointment" && !selectedVisit)} style={styles.button} onPress={() => act(() => mode === "appointment" ? api.linkAssessment(assessmentId, bookingId, message, request) : api.shareAssessment(assessmentId, doctor, message, request), mode === "appointment" ? "Assessment linked to the appointment's doctor." : "Assessment shared with the chosen doctor.")}><Text style={styles.white}>{busy ? "Saving…" : mode === "appointment" ? "Confirm appointment link" : "Confirm sharing"}</Text></Pressable>
      <Pressable accessibilityRole="button" disabled={busy} onPress={() => setConfirm(false)}><Text style={styles.link}>Cancel sharing</Text></Pressable>
    </View> : <Pressable accessibilityRole="button" disabled={busy || (mode === "doctor" ? alreadyShared : !selectedVisit || linked)} style={styles.button} onPress={() => setConfirm(true)}><Text style={styles.white}>{mode === "appointment" ? linked ? "Already linked to this appointment" : "Link selected appointment" : alreadyShared ? "Already shared with this doctor" : "Share this assessment"}</Text></Pressable>}
    <Text style={styles.label}>Sharing history & published reviews</Text>
    {shares.map(share => <View key={share.id} style={styles.record}>
      <Text style={styles.title}>{share.doctor_name} · {share.revoked_at ? "Revoked" : share.review ? "Reviewed" : "Awaiting review"}</Text>
      {share.visit ? <Text style={styles.body}>Linked appointment: {queueToken(share.visit)} · {visitTime(share.visit.starts_at)} · {share.visit.status}</Text> : <Text style={styles.body}>Direct doctor share</Text>}
      <Text style={styles.body}>Shared {visitTime(share.created_at)}{share.revoked_at ? ` · revoked ${visitTime(share.revoked_at)}` : ""}</Text>
      {share.patient_message ? <Text style={styles.body}>Your message: {share.patient_message}</Text> : null}
      {share.review ? <PublishedReview review={share.review}/> : null}
      {!share.revoked_at ? revoke === share.id ? <View><Text style={styles.body}>Revoke this doctor's future access to this assessment? Published reviews remain visible to you.</Text><Pressable accessibilityRole="button" disabled={busy} onPress={() => act(() => api.revokeShare(share.id), "Doctor access revoked.")}><Text style={styles.link}>Confirm revoke</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={() => setRevoke("")}><Text style={styles.link}>Keep sharing</Text></Pressable></View> : <Pressable accessibilityRole="button" disabled={busy} onPress={() => setRevoke(share.id)}><Text style={styles.link}>Revoke access</Text></Pressable> : null}
    </View>)}
    {!shares.length ? <Text style={styles.body}>No doctor has access to this assessment yet.</Text> : null}
  </View>;
}
const styles = StyleSheet.create({
  box: { borderTopWidth: 1, borderColor: "#dce6e0", marginTop: 20, paddingTop: 20 }, title: { color: "#19352e", fontWeight: "600", fontSize: 16, marginBottom: 8 },
  body: { color: "#637970", lineHeight: 20, fontSize: 13, marginVertical: 5 }, label: { fontWeight: "600", color: "#19352e", marginTop: 14, marginBottom: 8 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 }, choice: { backgroundColor: "#e7efeb", padding: 12, borderRadius: 10 }, selected: { backgroundColor: "#176f5e" },
  input: { borderWidth: 1, borderColor: "#ccdcd4", borderRadius: 10, padding: 12, minHeight: 85, textAlignVertical: "top", color: "#19352e" }, button: { backgroundColor: "#176f5e", padding: 14, borderRadius: 10, marginVertical: 12 }, white: { color: "white", fontWeight: "600" },
  link: { color: "#176f5e", fontWeight: "600", paddingVertical: 12 }, record: { backgroundColor: "#f4f7f6", padding: 14, borderRadius: 12, marginTop: 12 }, error: { backgroundColor: "#fff0f0", padding: 12, color: "#9f2929" }
});
