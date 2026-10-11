import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Care, DemoApi, DemoPatient, money, queueToken, visitTime } from "@smart-skin/shared";

import { apiBase as base } from "./apiConfig";
export default function CareView({ patient }: { patient: DemoPatient }) {
  const api = useMemo(() => new DemoApi(base, patient), [patient]);
  const [records, setRecords] = useState<Care[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true, fetching = false;
    async function load() {
      if (fetching) return; fetching = true;
      try { const data = await api.care(); if (active) { setRecords(data); setError(""); } }
      catch (e) { if (active) setError(e instanceof Error ? e.message : "Cannot load care records."); }
      finally { fetching = false; if (active) setLoading(false); }
    }
    void load(); const timer = setInterval(load, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [api]);
  async function refresh() {
    try { setRecords(await api.care()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot refresh."); }
  }
  async function pay(id: string) {
    if (busy) return; setBusy(true); setError(""); setNotice("");
    try { await api.paySimulated(id); setConfirm(""); setNotice("Simulated payment recorded. No money was transferred."); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to record simulation."); }
    finally { setBusy(false); }
  }
  const visible = records.filter(r => r.prescription || r.invoice);
  return <View>
    <View style={styles.heading}><Text style={styles.title}>Prescriptions & bills</Text><Pressable accessibilityRole="button" onPress={refresh}><Text style={styles.link}>Refresh care</Text></Pressable></View>
    <Text style={styles.muted}>Saved records from your doctor and staff. Placeholder items and payments are for demonstration only.</Text>
    {error ? <View accessibilityRole="alert" style={styles.error}><Text>{error}</Text><Pressable accessibilityRole="button" onPress={refresh}><Text style={styles.link}>Retry care connection</Text></Pressable></View> : null}
    {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    {loading ? <ActivityIndicator color="#176f5e" /> : null}
    {!loading && visible.length === 0 ? <View style={styles.card}><Text style={styles.subtitle}>No prescriptions or bills yet</Text><Text style={styles.muted}>Your issued prescription and bill will appear here after your visit is processed.</Text></View> : null}
    {visible.map(({ visit, prescription, invoice }) => <View key={visit.id} style={styles.card}>
      <Text style={styles.subtitle}>{queueToken(visit)} · {visit.doctor_name}</Text><Text style={styles.muted}>{visitTime(visit.starts_at)}</Text>
      <Text style={styles.section}>Prescription</Text>
      {prescription ? <><Text style={styles.status}>{prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing"}</Text>{prescription.items.map(item => <View key={item.medicine_id} style={styles.item}><Text style={styles.bold}>{item.name} × {item.quantity}</Text><Text style={styles.muted}>{item.directions}</Text></View>)}</> : <Text style={styles.muted}>No prescription issued.</Text>}
      <Text style={styles.section}>Bill · simulation</Text>
      {invoice ? <>{invoice.lines.map((line, i) => <View key={i} style={styles.line}><Text style={styles.lineName}>{line.description} × {line.quantity}</Text><Text style={styles.bold}>{money(line.quantity * line.unit_price_cents)}</Text></View>)}<Text style={styles.total}>Total {money(invoice.total_cents)}</Text><Text style={styles.status}>{invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}</Text>
        {invoice.status === "paid" ? <Text style={styles.muted}>Demo receipt {invoice.id.slice(0, 8)}{invoice.paid_at ? ` · ${visitTime(invoice.paid_at)}` : ""}</Text> : prescription?.status === "issued" ? <Text style={styles.muted}>Staff must dispense the items before simulated payment.</Text> : confirm === invoice.id ? <><Text style={styles.muted}>Confirm simulated payment of {money(invoice.total_cents)}? No bank or payment service is involved.</Text><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => pay(invoice.id)}><Text style={styles.buttonText}>{busy ? "Saving…" : "Confirm simulated payment"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={() => setConfirm("")}><Text style={styles.link}>Keep unpaid</Text></Pressable></> : <Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => setConfirm(invoice.id)}><Text style={styles.buttonText}>Simulate payment</Text></Pressable>}
      </> : <Text style={styles.muted}>Staff has not generated your bill yet.</Text>}
    </View>)}
  </View>;
}

const styles = StyleSheet.create({
  heading: { flexDirection: "row", justifyContent: "space-between", flexWrap: "wrap", gap: 8 },
  title: { fontSize: 23, fontWeight: "700", color: "#19352e" }, subtitle: { fontSize: 17, fontWeight: "600", color: "#19352e", marginBottom: 8 },
  muted: { fontSize: 13, color: "#637970", lineHeight: 20 }, link: { color: "#176f5e", fontWeight: "600", paddingVertical: 10 },
  card: { backgroundColor: "white", padding: 20, borderWidth: 1, borderColor: "#dce6e0", borderRadius: 16, marginTop: 16 },
  section: { fontSize: 16, fontWeight: "600", color: "#19352e", marginTop: 22, marginBottom: 10 },
  status: { color: "#176f5e", fontWeight: "600", marginBottom: 10 }, item: { marginVertical: 7 }, bold: { fontWeight: "600", color: "#19352e" },
  line: { flexDirection: "row", justifyContent: "space-between", gap: 12, marginBottom: 10 }, lineName: { flex: 1, color: "#637970", fontSize: 13 },
  total: { borderTopWidth: 1, borderTopColor: "#dce6e0", paddingTop: 12, fontSize: 18, fontWeight: "700", marginVertical: 12, color: "#19352e" },
  button: { backgroundColor: "#176f5e", padding: 14, borderRadius: 10, alignItems: "center", marginTop: 14 }, buttonText: { color: "white", fontWeight: "600" },
  error: { backgroundColor: "#fff0f0", padding: 14, borderRadius: 12, marginTop: 14 }, notice: { backgroundColor: "#e7f4ed", color: "#176f5e", padding: 14, borderRadius: 12, marginTop: 14 }
});
