import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Booking } from "@smart-skin/shared";
import { readyForCheckout } from "./patientCheckoutStatus";

export default function PatientCheckoutUpdate({ visit }: { visit: Booking }) {
  if (!readyForCheckout(visit)) return null;
  return <View style={styles.notice} accessibilityLiveRegion="polite"><Text style={styles.text}>Consultation finished — please proceed to the counter.</Text></View>;
}

const styles = StyleSheet.create({
  notice: { marginTop: 12, padding: 12, backgroundColor: "#eaf6ef", borderRadius: 10, borderWidth: 1, borderColor: "#b9d8c8" },
  text: { fontSize: 14, color: "#176f5e", lineHeight: 21, fontWeight: "600" },
});
