import React, { useEffect, useMemo, useState } from "react";
import { Image, Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { File, Paths } from "expo-file-system";
import { Assessment, DemoApi, DemoPatient, visitTime } from "@smart-skin/shared";

import { apiBase as base } from "./apiConfig";
type Draft = { uri: string; mime: string; file?: globalThis.File; request: string; local?: File };
export default function SkinView({ patient }: { patient: DemoPatient }) {
  const api = useMemo(() => new DemoApi(base, patient), [patient]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [history, setHistory] = useState<Assessment[]>([]);
  const [result, setResult] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [denied, setDenied] = useState(false);
  useEffect(() => () => { if (draft?.local?.exists) draft.local.delete(); }, [draft]);
  useEffect(() => { let active = true; api.assessments().then(data => { if (active) setHistory(data); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [api]);
  async function refresh() {
    try { setHistory(await api.assessments()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot load history."); }
  }
  function discard() {
    if (draft?.local?.exists) draft.local.delete();
    setDraft(null); setNotice("Photo discarded. No assessment was saved.");
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
      if (Platform.OS !== "web") { local = new File(Paths.cache, `${request}.${mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg"}`); new File(asset.uri).copy(local); }
      if (draft?.local?.exists) draft.local.delete();
      setDraft({ uri: local?.uri || asset.uri, mime, file: asset.file, local, request }); setResult(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to select a photo. Retry or use the gallery."); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!draft || busy) return; setBusy(true); setError(""); setNotice("");
    try {
      const form = new FormData();
      form.append("request_id", draft.request);
      if (Platform.OS === "web") {
        if (!draft.file) throw new Error("Please choose the photo again; browser file is unavailable.");
        form.append("photo", draft.file, "demo-photo");
      } else {
        // Expo's fetch reads File bytes; legacy React Native URI objects are unsupported.
        form.append("photo", draft.local ?? new File(draft.uri));
      }
      const saved = await api.saveAssessment(form);
      setResult(saved); setHistory(current => [saved, ...current.filter(r => r.id !== saved.id)]);
      if (draft.local?.exists) draft.local.delete();
      setDraft(null); setNotice("Photo and simulated result saved to your local project backend.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to save. Refresh history before retrying."); }
    finally { setBusy(false); }
  }
  async function open(id: string) {
    if (busy) return; setBusy(true); setError("");
    try { setResult(await api.assessment(id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot open assessment."); }
    finally { setBusy(false); }
  }
  return <View>
    <Text style={styles.title}>Skin assessment</Text><Text style={styles.muted}>Capture or select a demonstration photo, preview it, then save. Use synthetic or non-sensitive images while demo identities are in use.</Text>
    <View style={styles.warning}><Text style={styles.warningText}>SIMULATION — no trained model or image analysis. Example category is not a diagnosis. Saved photos stay on this computer's local backend.</Text></View>
    {error ? <View accessibilityRole="alert" style={styles.error}><Text>{error}</Text>{denied && Platform.OS !== "web" ? <Pressable accessibilityRole="button" onPress={() => Linking.openSettings()}><Text style={styles.link}>Open app settings</Text></Pressable> : null}</View> : null}
    {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    <View style={styles.row}><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => pick(true)}><Text style={styles.buttonText}>Take photo</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={styles.secondary} onPress={() => pick(false)}><Text style={styles.link}>Choose photo</Text></Pressable></View>
    {draft ? <View style={styles.card}><Text style={styles.subtitle}>Confirm your photo</Text><Image accessibilityLabel="Selected photo preview" source={{ uri: draft.uri }} style={styles.photo} resizeMode="contain" /><Text style={styles.muted}>JPEG, PNG or WebP · maximum 5 MB. Confirming sends the photo only to your local project backend and saves a simulated result.</Text><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={save}><Text style={styles.buttonText}>{busy ? "Saving…" : "Save simulated assessment"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={discard}><Text style={styles.link}>Discard preview</Text></Pressable></View> : null}
    {result ? <View style={styles.card}><Text style={styles.subtitle}>Saved result · SIMULATION</Text><Text style={styles.muted}>{visitTime(result.created_at)}</Text>{result.photo_uri ? <Image accessibilityLabel="Saved assessment photo" source={{ uri: result.photo_uri }} style={styles.photo} resizeMode="contain" /> : null}<Text style={styles.subtitle}>{result.example_category}</Text><Text style={styles.muted}>{result.message}</Text><Text style={styles.muted}>This fixed example does not depend on your photo. Real model inference and doctor review are later work.</Text></View> : null}
    <View style={[styles.row, { marginTop: 24 }]}><Text style={styles.title}>Assessment history</Text><Pressable accessibilityRole="button" disabled={busy} onPress={refresh}><Text style={styles.link}>Refresh history</Text></Pressable></View><Text style={styles.muted}>Your latest 100 saved assessments. Photos survive app/server restarts because they are saved in the shared database.</Text>
    {history.map(item => <Pressable accessibilityRole="button" accessibilityLabel={`Open assessment ${item.id.slice(0, 8)}`} key={item.id} disabled={busy} style={styles.card} onPress={() => open(item.id)}><Text style={styles.subtitle}>{visitTime(item.created_at)}</Text><Text style={styles.muted}>Simulation · {item.example_category}</Text><Text style={styles.link}>View saved photo & result →</Text></Pressable>)}
    {!history.length ? <Text style={[styles.muted, { marginTop: 15 }]}>No saved assessments yet.</Text> : null}
  </View>;
}
const styles = StyleSheet.create({
  title: { fontSize: 23, fontWeight: "700", color: "#19352e", marginBottom: 8 }, subtitle: { fontSize: 16, fontWeight: "600", color: "#19352e", marginBottom: 8 },
  muted: { color: "#637970", fontSize: 13, lineHeight: 20 }, warning: { backgroundColor: "#fff3db", padding: 14, borderRadius: 12, marginVertical: 16 }, warningText: { color: "#825b16", fontSize: 13, lineHeight: 20 },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12 }, button: { backgroundColor: "#176f5e", padding: 14, borderRadius: 10, marginVertical: 8 }, buttonText: { color: "white", fontWeight: "600" },
  secondary: { backgroundColor: "#e7efeb", paddingHorizontal: 14, borderRadius: 10 }, link: { color: "#176f5e", fontWeight: "600", paddingVertical: 10 },
  card: { backgroundColor: "white", padding: 18, borderWidth: 1, borderColor: "#dce6e0", borderRadius: 16, marginTop: 16 }, photo: { width: "100%", height: 240, marginVertical: 12, backgroundColor: "#f4f7f6", borderRadius: 10 },
  error: { backgroundColor: "#fff0f0", padding: 14, borderRadius: 12, marginBottom: 12 }, notice: { color: "#176f5e", backgroundColor: "#e7f4ed", padding: 14, borderRadius: 12, marginBottom: 12 }
});
