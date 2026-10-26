"use client";
import { useEffect, useState } from "react";
import { Booking, DemoActor, DemoApi, visitTime } from "@smart-skin/shared";

export default function PrescribingBackground({ api, actor, visit, busy }: { api: DemoApi; actor: DemoActor; visit: Booking; busy: boolean }) {
  const allowed = actor.startsWith("doctor-") && visit.doctor_id === actor;
  const [data, setData] = useState<{ allergies: string; medicines: string; updated_at: string | null } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null); setError(""); setLoading(true);
    // Do not fetch for staff or another doctor. The existing consultation API also enforces this scope.
    if (!allowed) return () => { active = false; };
    void api.consultation(visit.id).then(result => {
      if (!result.background || typeof result.background.medicines !== "string") throw new Error("Patient information is unavailable.");
      if (active) setData({ allergies: result.background.allergies, medicines: result.background.medicines, updated_at: result.background.updated_at });
    }).catch(e => {
      if (active) setError(e instanceof Error ? e.message : "Cannot load patient information.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, visit.id, allowed, refresh]);
  if (!allowed) return null;

  return <section aria-label="Patient-reported prescribing information" className="mb-4 rounded-lg border border-[#ccdcd4] bg-white p-3">
    <h4 className="font-semibold">Patient-reported information</h4>
    <p className="muted my-2 text-xs">From the patient’s current medical background, not a snapshot of this visit. Refresh to check for changes.</p>
    {loading ? <p role="status" className="text-sm">Loading patient information…</p> : error ? <p role="alert" className="text-sm text-red-800">Patient information unavailable. {error} Refresh to retry.</p> : data ? <>
      <dl className="space-y-3 text-sm">
        <div><dt className="font-semibold">Allergies</dt><dd className="mt-1 whitespace-pre-wrap break-words">{data.allergies.trim() || "Not provided"}</dd></div>
        <div><dt className="font-semibold">Current medicines</dt><dd className="mt-1 whitespace-pre-wrap break-words">{data.medicines.trim() || "Not provided"}</dd></div>
      </dl>
      <p className="muted mt-2 text-xs">{data.updated_at ? `Background last saved ${visitTime(data.updated_at)}.` : "No medical background saved yet."} {!data.allergies.trim() || !data.medicines.trim() ? "Not provided means this information has not been saved." : ""}</p>
    </> : null}
    <button type="button" className="mt-3 text-sm font-semibold underline" disabled={busy || loading} onClick={() => setRefresh(value => value + 1)}>Refresh patient information</button>
  </section>;
}
