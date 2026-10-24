import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Care, DemoApi, DemoPatient, medicineLabel, money, queueToken, visitTime } from "@smart-skin/shared";

import { apiBase as base } from "./apiConfig";
import { CareFilter, CareOrder, careFilterLabels, careOrderLabels, filterCare, sortCare, summarizeCare } from "./patientCareFilter";
import BookingDateFilter from "./BookingDateFilter";
export default function CareView({ patient }: { patient: DemoPatient }) {
  const api = useMemo(() => new DemoApi(base, patient), [patient]);
  const [records, setRecords] = useState<Care[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<CareFilter>("all");
  const [query, setQuery] = useState("");
  const [date, setDate] = useState<string | null>(null);
  const [order, setOrder] = useState<CareOrder>("newest");
  const [expandedId, setExpandedId] = useState("");
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
  const all = filterCare(records, "all");
  const visible = sortCare(filterCare(records, status, query, queueToken, date), order);
  const summary = summarizeCare(visible);
  function changeStatus(value: CareFilter) {
    if (busy) return;
    setStatus(value); setConfirm(""); setNotice("");
  }
  return <View>
    <View style={styles.heading}><Text style={styles.title}>Prescriptions & bills</Text><Pressable accessibilityRole="button" onPress={refresh}><Text style={styles.link}>Refresh care</Text></Pressable></View>
    <Text style={styles.muted}>Saved records from your doctor and staff. Placeholder items and payments are for demonstration only.</Text>
    <View style={styles.card}>
      <Text style={styles.subtitle}>Find care records</Text>
      <Text style={styles.muted}>Search by doctor or queue number.</Text>
      <TextInput accessibilityLabel="Search care records by doctor or queue number" placeholder="Doctor or queue number, e.g. L001" value={query} onChangeText={value => { if (!busy) { setQuery(value); setConfirm(""); setNotice(""); } }} editable={!busy} autoCapitalize="none" autoCorrect={false} maxLength={100} style={styles.input}/>
      <BookingDateFilter key={date || "all"} value={date} busy={busy} allowPast title="Appointment date" onChange={value => { if (!busy) { setDate(value); setConfirm(""); setNotice(""); } }}/>
      <Text style={styles.muted}>Filter by your visit date in Malaysia time, rather than when the bill was issued or paid.</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel="Care record status" style={styles.filters}>{(Object.keys(careFilterLabels) as CareFilter[]).map(key => <Pressable key={key} accessibilityRole="radio" aria-checked={status === key} accessibilityState={{checked: status === key, disabled: busy}} disabled={busy} onPress={() => changeStatus(key)} style={[styles.choice, status === key && styles.active, busy && {opacity: .45}]}><Text style={styles.link}>{careFilterLabels[key]}</Text></Pressable>)}</View>
      <Text style={styles.muted}>Unpaid bills shows generated bills only. Records awaiting a bill remain under All records.</Text>
      <Text style={styles.section}>Care record order</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel="Care record order" style={styles.filters}>{(Object.keys(careOrderLabels) as CareOrder[]).map(key => <Pressable key={key} accessibilityRole="radio" aria-checked={order === key} accessibilityState={{checked: order === key, disabled: busy}} disabled={busy} onPress={() => { if (!busy) { setOrder(key); setConfirm(""); setNotice(""); } }} style={[styles.choice, order === key && styles.active, busy && {opacity: .45}]}><Text style={styles.link}>{careOrderLabels[key]}</Text></Pressable>)}</View>
      <Text style={styles.muted}>Sorted by appointment time. Reset care filters keeps your chosen order.</Text>
      <Pressable accessibilityRole="button" disabled={busy || (status === "all" && !query && !date)} onPress={() => { if (!busy) { setQuery(""); setDate(null); changeStatus("all"); } }} style={(busy || (status === "all" && !query && !date)) && {opacity: .45}}><Text style={styles.link}>Reset care filters</Text></Pressable>
      {!loading ? <Text style={styles.muted}>Showing {visible.length} of {all.length} care records</Text> : null}
    </View>
    {error ? <View accessibilityRole="alert" style={styles.error}><Text>{error}</Text><Pressable accessibilityRole="button" onPress={refresh}><Text style={styles.link}>Retry care connection</Text></Pressable></View> : null}
    {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    {loading ? <ActivityIndicator color="#176f5e" /> : null}
    {!loading && !error ? <View style={styles.card}>
      <Text style={styles.subtitle}>Summary of shown care records</Text>
      <Text style={styles.muted}>Follows your search, status and appointment-date filters. Amounts include generated bills only; no real money is transferred.</Text>
      <View style={styles.summaryRow}>
        <View style={styles.summaryItem}><Text style={styles.muted}>Total unpaid</Text><Text style={styles.summaryValue}>{money(summary.unpaidCents)}</Text></View>
        <View style={styles.summaryItem}><Text style={styles.muted}>Total paid · simulation</Text><Text style={styles.summaryValue}>{money(summary.paidCents)}</Text></View>
        <View style={styles.summaryItem}><Text style={styles.muted}>Prescriptions awaiting dispensing</Text><Text style={styles.summaryValue}>{summary.awaitingDispensing}</Text></View>
      </View>
    </View> : null}
    {!loading && all.length === 0 ? <View style={styles.card}><Text style={styles.subtitle}>No prescriptions or bills yet</Text><Text style={styles.muted}>Your issued prescription and bill will appear here after your visit is processed.</Text></View> : !loading && visible.length === 0 ? <View style={styles.card}><Text style={styles.subtitle}>No matching care records</Text><Text style={styles.muted}>Change your search, status or appointment date, or reset care filters to see all your prescriptions and bills.</Text></View> : null}
    {visible.map(({ visit, prescription, invoice }) => <View key={visit.id} style={styles.card}>
      <Text style={styles.subtitle}>{queueToken(visit)} · {visit.doctor_name}</Text><Text style={styles.muted}>{visitTime(visit.starts_at)}</Text>
      <Text style={styles.compactStatus}>Prescription: {prescription ? prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing" : "Not issued"}</Text>
      <Text style={styles.muted}>{invoice ? `Bill: ${money(invoice.total_cents)} · ${invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}` : "Bill: Not generated yet"}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel={`${expandedId === visit.id ? "Hide" : "View"} details for ${queueToken(visit)}, ${visit.doctor_name}, ${visitTime(visit.starts_at)}`} aria-expanded={expandedId === visit.id} accessibilityState={{expanded: expandedId === visit.id, disabled: busy}} disabled={busy} onPress={() => { if (!busy) { setExpandedId(expandedId === visit.id ? "" : visit.id); setConfirm(""); } }} style={busy && {opacity: .45}}><Text style={styles.link}>{expandedId === visit.id ? "Hide details" : "View details"}</Text></Pressable>
      {expandedId === visit.id ? <>
      <Text style={styles.section}>Prescription</Text>
      {prescription ? <><Text style={styles.status}>{prescription.status === "dispensed" ? "Dispensed" : "Issued — awaiting dispensing"}</Text>{prescription.items.map(item => <View key={item.medicine_id} style={styles.item}><Text style={styles.bold}>{medicineLabel(item)} × {item.quantity}</Text><Text style={styles.muted}>{item.directions}</Text></View>)}</> : <Text style={styles.muted}>No prescription issued.</Text>}
      <Text style={styles.section}>Bill · simulation</Text>
      {invoice ? <>{invoice.lines.map((line, i) => <View key={i} style={styles.line}><Text style={styles.lineName}>{line.description} × {line.quantity}</Text><Text style={styles.bold}>{money(line.quantity * line.unit_price_cents)}</Text></View>)}<Text style={styles.total}>Total {money(invoice.total_cents)}</Text><Text style={styles.status}>{invoice.status === "paid" ? "Paid · simulation" : "Unpaid"}</Text>
        {invoice.status === "paid" ? <Text style={styles.muted}>Demo receipt {invoice.id.slice(0, 8)}{invoice.paid_at ? ` · ${visitTime(invoice.paid_at)}` : ""}</Text> : prescription?.status === "issued" ? <Text style={styles.muted}>Staff must dispense the items before simulated payment.</Text> : confirm === invoice.id ? <><Text style={styles.muted}>Confirm simulated payment of {money(invoice.total_cents)}? No bank or payment service is involved.</Text><Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => pay(invoice.id)}><Text style={styles.buttonText}>{busy ? "Saving…" : "Confirm simulated payment"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={() => setConfirm("")}><Text style={styles.link}>Keep unpaid</Text></Pressable></> : <Pressable accessibilityRole="button" disabled={busy} style={styles.button} onPress={() => setConfirm(invoice.id)}><Text style={styles.buttonText}>Simulate payment</Text></Pressable>}
      </> : <Text style={styles.muted}>Staff has not generated your bill yet.</Text>}
      </> : null}
    </View>)}
  </View>;
}

const styles = StyleSheet.create({
  heading: { flexDirection: "row", justifyContent: "space-between", flexWrap: "wrap", gap: 8 },
  compactStatus: { color: "#176f5e", fontWeight: "600", marginTop: 12, marginBottom: 6 },
  summaryRow: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 14 },
  summaryItem: { flexGrow: 1, flexBasis: 140, backgroundColor: "#edf5f0", borderRadius: 10, padding: 14 },
  summaryValue: { fontSize: 21, fontWeight: "700", color: "#19352e", marginTop: 8 },
  input: { padding: 12, borderWidth: 1, borderColor: "#ccdcd4", borderRadius: 10, color: "#19352e", marginTop: 8, marginBottom: 12 },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  choice: { paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: "#dce6e0", backgroundColor: "#e7efeb" },
  active: { borderWidth: 2, borderColor: "#176f5e" },
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
