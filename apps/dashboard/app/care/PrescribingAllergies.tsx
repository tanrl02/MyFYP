"use client";
import { useEffect, useState } from "react";
import { Booking, DemoActor, DemoApi, visitTime } from "@smart-skin/shared";

export default function PrescribingAllergies({ api, actor, visit, busy }: { api: DemoApi; actor: DemoActor; visit: Booking; busy: boolean }) {
  const allowed = (actor === "doctor-lim" || actor === "doctor-anita") && visit.doctor_id === actor;
  const [data, setData] = useState<{ allergies: string; updated_at: string | null } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null); setError(""); setLoading(true);
    // Do not fetch for staff or another doctor. The existing consultation API also enforces this scope.
    if (!allowed) return () => { active = false; };
    void api.consultation(visit.id).then(result => {
      if (!result.background) throw new Error("Allergy information is unavailable.");
      if (active) setData({ allergies: result.background.allergies, updated_at: result.background.updated_at });
    }).catch(e => {
      if (active) setError(e instanceof Error ? e.message : "Cannot load allergy information.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, visit.id, allowed, refresh]);
  if (!allowed) return null;

  return <section aria-label="Patient-reported allergies" className="mb-4 rounded-lg border border-[#ccdcd4] bg-white p-3">
    <h4 className="font-semibold">Patient-reported allergies</h4>
    <p className="muted my-2 text-xs">From the patient’s current medical background, not a snapshot of this visit. Refresh to check for changes.</p>
    {loading ? <p role="status" className="text-sm">Loading allergy information…</p> : error ? <p role="alert" className="text-sm text-red-800">Allergy information unavailable. {error} Refresh to retry.</p> : data ? <>
      <p className="whitespace-pre-wrap break-words text-sm">{data.allergies.trim() || "Not provided"}</p>
      <p className="muted mt-2 text-xs">{data.updated_at ? `Background last saved ${visitTime(data.updated_at)}.` : "No medical background saved yet."} {!data.allergies.trim() ? "Not provided means no allergy information has been saved." : ""}</p>
    </> : null}
    <button type="button" className="mt-3 text-sm font-semibold underline" disabled={busy || loading} onClick={() => setRefresh(value => value + 1)}>Refresh allergy information</button>
  </section>;
}
