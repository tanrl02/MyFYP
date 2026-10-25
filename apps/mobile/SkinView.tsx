import React, { useEffect, useMemo, useState } from "react";
import { Image, Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { File, Paths } from "expo-file-system";
import { Assessment, DemoApi, DemoPatient, PhotoCheck, assessmentCategory, assessmentOrigin, visitTime } from "@smart-skin/shared";

import { apiBase as base } from "./apiConfig";
import SharingView from "./SharingView";
import AssessmentResult from "./AssessmentResult";
import SymptomsForm,{emptySymptoms} from "./SymptomsForm";
import BookingDateFilter from "./BookingDateFilter";
import {filterAssessmentHistory} from "./patientAssessmentFilter";
type Draft = { uri: string; mime: string; file?: globalThis.File; request: string; local?: File };
function photoForm(photo:Draft) {
  const form=new FormData();
  if(Platform.OS==="web") {
    if(!photo.file)throw new Error("Please choose the photo again; browser file is unavailable.");
    form.append("photo",photo.file,"photo-check");
  } else {
    const source=photo.local??new File(photo.uri);
    if(!source.exists)throw new Error("The preview photo is no longer available. Take or choose the photo again.");
    form.append("photo",source);
  }
  return form;
}
export default function SkinView({ patient, initialAssessmentId, onFindDoctor }: { patient: DemoPatient; initialAssessmentId?: string; onFindDoctor?:(assessmentId:string)=>void }) {
  const api = useMemo(() => new DemoApi(base, patient), [patient]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [history, setHistory] = useState<Assessment[]>([]);
  const [historyDate,setHistoryDate]=useState<string|null>(null);
  const visibleHistory=filterAssessmentHistory(history,historyDate);
  const [result, setResult] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking,setChecking]=useState(false);
  const [symptoms,setSymptoms]=useState(emptySymptoms);
  const [symptomsLocked,setSymptomsLocked]=useState(false);
  const symptomsComplete=Boolean(symptoms.body_area.trim()&&symptoms.onset.trim());
  const [photoCheck,setPhotoCheck]=useState<PhotoCheck|null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [denied, setDenied] = useState(false);
  useEffect(() => () => { if (draft?.local?.exists) draft.local.delete(); }, [draft]);
  useEffect(() => { let active = true; api.assessments().then(data => { if (active) setHistory(data); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [api]);
  useEffect(()=>{if(!initialAssessmentId)return;let active=true;setBusy(true);setResult(null);api.assessment(initialAssessmentId).then(data=>{if(active)setResult(data);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setBusy(false);});return()=>{active=false;};},[api,initialAssessmentId]);
  async function refresh() {
    try { setHistory(await api.assessments()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot load history."); }
  }
  function discard() {
    if (draft?.local?.exists) draft.local.delete();
    setDraft(null);setPhotoCheck(null);setSymptoms(emptySymptoms());setSymptomsLocked(false); setNotice(symptomsLocked?"Preview discarded. Refresh history if you previously attempted to save.":"Photo discarded. No assessment was saved.");
  }
  async function validate(selected:Draft) {
    setChecking(true);setPhotoCheck(null);
    try {setPhotoCheck(await api.checkPhoto(photoForm(selected)));}
    finally {setChecking(false);}
  }
  async function retryCheck() {
    if(!draft||busy)return;setBusy(true);setError("");
    try {await validate(draft);}
    catch(e){setError(e instanceof Error?e.message:"Photo checking failed. Retry before saving.");}
    finally{setBusy(false);}
  }
  async function pick(camera: boolean) {
    if (busy) return; setBusy(true); setError(""); setNotice(""); setDenied(false);
    try {
      if (camera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) { setDenied(!permission.canAskAgain); setError("Camera permission was denied. You can retry or choose a gallery photo."); return; }
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], allowsEditing: false, quality: 0.8, exif: false };
      const selection = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
      if (selection.canceled) { setNotice("Selection cancelled. Your previous preview is unchanged."); return; }
      const asset = selection.assets[0];
      const size = asset.fileSize ?? (Platform.OS !== "web" ? new File(asset.uri).size : asset.file?.size);
      if (size && size > 5 * 1024 * 1024) throw new Error("Choose a JPEG, PNG or WebP photo up to 5 MB.");
      const mime = asset.mimeType || "image/jpeg";
      if (!["image/jpeg", "image/png", "image/webp"].includes(mime)) throw new Error("Choose a JPEG, PNG or WebP photo. Other formats are not supported yet.");
      const request = `photo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      let local: File | undefined;
      if (Platform.OS !== "web") {
        local = new File(Paths.cache, `${request}.${mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg"}`);
        // Expo's native copy is asynchronous: publish/check only after bytes exist.
        await new File(asset.uri).copy(local);
        if(!local.exists)throw new Error("Could not prepare the photo. Take or choose it again.");
      }
      if (draft?.local?.exists) draft.local.delete();
      const selected={ uri: local?.uri || asset.uri, mime, file: asset.file, local, request };
      setDraft(selected);setPhotoCheck(null);setResult(null);setSymptoms(emptySymptoms());setSymptomsLocked(false);
      await validate(selected);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to select a photo. Retry or use the gallery."); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!draft || busy || !photoCheck?.accepted || !symptomsComplete) return; setBusy(true); setError(""); setNotice("");
    try {
      const form = photoForm(draft);
      form.append("request_id", draft.request);
      form.append("symptoms",JSON.stringify({...symptoms,body_area:symptoms.body_area.trim(),onset:symptoms.onset.trim(),description:symptoms.description.trim()}));
      setSymptomsLocked(true);
      const saved = await api.saveAssessment(form);
      setResult(saved); setHistory(current => [saved, ...current.filter(r => r.id !== saved.id)]);
      if (draft.local?.exists) draft.local.delete();
      setDraft(null);setPhotoCheck(null); setNotice("Photo, symptom details and experimental AI suggestions saved. You can share them with a doctor for review.");
    } catch (e) { setPhotoCheck(null); setError(e instanceof Error ? e.message : "Unable to save. Refresh history before retrying."); }
    finally { setBusy(false); }
  }
  async function open(id: string) {
    if (busy) return; setBusy(true); setError("");
    try { setResult(await api.assessment(id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot open assessment."); }
    finally { setBusy(false); }
  }
  return <View>
    <Text style={styles.title}>Skin assessment</Text><Text style={styles.muted}>Take or choose a non-sensitive close-up skin photo. Automatic checks run on your local backend before you can save. Avoid objects, screens, glare and identifying details.</Text>
    <View style={styles.warning}><Text style={styles.warningText}>EXPERIMENTAL AI — new assessments use a research model and can be wrong. Photo quality/skin checks are separate. A doctor should review the result. Older records remain labelled simulations.</Text></View>
    {error ? <View accessibilityRole="alert" style={styles.error}><Text>{error}</Text>{denied && Platform.OS !== "web" ? <Pressable accessibilityRole="button" onPress={() => Linking.openSettings()}><Text style={styles.link}>Open app settings</Text></Pressable> : null}</View> : null}
    {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    <View style={styles.row}><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => pick(true)}><Text style={styles.buttonText}>Take photo</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={styles.secondary} onPress={() => pick(false)}><Text style={styles.link}>Choose photo</Text></Pressable></View>
    {draft ? <View style={styles.card}><Text style={styles.subtitle}>{checking?"Checking photo…":photoCheck?.accepted?"Photo checks passed":photoCheck?"Retake required":"Photo not checked"}</Text><Image accessibilityLabel="Selected photo preview" source={{ uri: draft.uri }} style={styles.photo} resizeMode="contain" />
      {checking?<Text accessibilityRole="alert" style={styles.muted}>Checking detail, lighting and skin content. The first check can take longer while the local model loads.</Text>:null}
      {photoCheck?<View accessibilityRole="alert" style={photoCheck.accepted?styles.notice:styles.error}><Text>{photoCheck.message}</Text>{photoCheck.reasons.map(reason=><Text key={reason}>{reason}</Text>)}</View>:null}
      <Text style={styles.muted}>JPEG, PNG or WebP · up to 5 MB · at least 224 pixels per side. Checking does not save an assessment. Save rechecks the uploaded photo.</Text>
      <SymptomsForm value={symptoms} onChange={setSymptoms} disabled={busy||symptomsLocked}/>{symptomsLocked?<Text style={styles.muted}>Details are locked for this save attempt. Retry unchanged, or refresh history before starting again.</Text>:null}
      {!photoCheck?.accepted&&!checking?<Pressable accessibilityRole="button" disabled={busy} onPress={retryCheck}><Text style={styles.link}>Retry photo check</Text></Pressable>:null}
      {photoCheck&&!photoCheck.accepted?<Pressable accessibilityRole="button" disabled={busy} onPress={()=>pick(true)}><Text style={styles.link}>Retake photo</Text></Pressable>:null}
      <Pressable accessibilityRole="button" disabled={busy||!photoCheck?.accepted||!symptomsComplete} style={[styles.button,(!photoCheck?.accepted||!symptomsComplete)&&styles.disabled]} onPress={save}><Text style={styles.buttonText}>{checking?"Checking…":busy?"Analysing & saving…":"Analyse & save assessment"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={discard}><Text style={styles.link}>Discard preview</Text></Pressable></View> : null}
    {result ? <View style={styles.card}><Text style={styles.subtitle}>Saved result · {assessmentOrigin(result)}</Text><Text style={styles.muted}>{visitTime(result.created_at)}</Text>{result.photo_uri ? <Image accessibilityLabel="Saved assessment photo" source={{ uri: result.photo_uri }} style={styles.photo} resizeMode="contain" /> : null}<AssessmentResult assessment={result}/><Pressable accessibilityRole="button" disabled={busy||!onFindDoctor} style={styles.button} onPress={()=>onFindDoctor?.(result.id)}><Text style={styles.buttonText}>Find a suitable doctor</Text></Pressable><Text style={styles.muted}>Doctor suggestions use the saved result and staff-entered expertise. You can choose a different concern. Booking does not share the assessment; authorise access separately.</Text><SharingView key={result.id} patient={patient} assessmentId={result.id} /></View> : null}
    <View style={[styles.row, { marginTop: 24 }]}><Text style={styles.title}>Assessment history</Text><Pressable accessibilityRole="button" disabled={busy} onPress={refresh}><Text style={styles.link}>Refresh history</Text></Pressable></View><Text style={styles.muted}>Your latest 100 saved assessments. Photos survive app/server restarts because they are saved in the shared database.</Text>
    <BookingDateFilter key={historyDate||"all"} value={historyDate} onChange={setHistoryDate} busy={busy} allowPast title="Assessment saved date" monthContext="assessment" calendarHint="Choose the Malaysia date when the assessment was saved. This filters the history list only."/>
    <Text accessibilityLiveRegion="polite" style={styles.muted}>Showing {visibleHistory.length} of {history.length} loaded assessments</Text>
    {visibleHistory.map(item => <Pressable accessibilityRole="button" accessibilityLabel={`Open assessment ${item.id.slice(0, 8)}`} key={item.id} disabled={busy} style={styles.card} onPress={() => open(item.id)}><Text style={styles.subtitle}>{visitTime(item.created_at)}</Text><Text style={styles.muted}>{assessmentOrigin(item)} · {assessmentCategory(item)}</Text><Text style={styles.link}>View saved photo & suggestions →</Text></Pressable>)}
    {history.length&&!visibleHistory.length?<Text style={[styles.muted,{marginTop:15}]}>No loaded assessments saved on this Malaysia date. Choose another date or use Show all dates.</Text>:null}
    {!history.length ? <Text style={[styles.muted, { marginTop: 15 }]}>No saved assessments yet.</Text> : null}
  </View>;
}
const styles = StyleSheet.create({
  title: { fontSize: 23, fontWeight: "700", color: "#19352e", marginBottom: 8 }, subtitle: { fontSize: 16, fontWeight: "600", color: "#19352e", marginBottom: 8 },
  muted: { color: "#637970", fontSize: 13, lineHeight: 20 }, warning: { backgroundColor: "#fff3db", padding: 14, borderRadius: 12, marginVertical: 16 }, warningText: { color: "#825b16", fontSize: 13, lineHeight: 20 },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12 }, button: { backgroundColor: "#176f5e", padding: 14, borderRadius: 10, marginVertical: 8 }, buttonText: { color: "white", fontWeight: "600" },
  secondary: { backgroundColor: "#e7efeb", paddingHorizontal: 14, borderRadius: 10 }, link: { color: "#176f5e", fontWeight: "600", paddingVertical: 10 },
  card: { backgroundColor: "white", padding: 18, borderWidth: 1, borderColor: "#dce6e0", borderRadius: 16, marginTop: 16 }, photo: { width: "100%", height: 240, marginVertical: 12, backgroundColor: "#f4f7f6", borderRadius: 10 },
  error: { backgroundColor: "#fff0f0", padding: 14, borderRadius: 12, marginBottom: 12 }, notice: { color: "#176f5e", backgroundColor: "#e7f4ed", padding: 14, borderRadius: 12, marginBottom: 12 },disabled:{opacity:.4}
});
