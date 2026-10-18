# Independent doctor assessment in reviews

18 October 2026. The review flow now has a separate, doctor-entered assessment, notes and follow-up. The AI ranking remains its original experimental snapshot. A published doctor assessment is not an automatic AI diagnosis or a model correction.

## Doctor flow

1. Dashboard → `/reviews` → choose the authorised doctor → open a patient-shared assessment.
2. Review the photo independently. Enter **Doctor’s assessment** (up to500 characters), **Review note** and **Follow-up**. The assessment starts blank; it is never copied from the AI. Uncertainty such as “unable to determine from the photo” is allowed.
3. **Save draft** stores all three fields privately. **Reload saved draft** restores them. Version checks include assessment-only edits, so a stale tab cannot overwrite another saved assessment.
4. **Publish review** shows all three fields for confirmation. **Confirm publish** atomically publishes them, removes the private draft and sends the existing patient notification. Published content cannot be replaced; exact retries return the same review.

## Patient flow

Patient → Skin check → saved assessment → Doctor sharing & review. Published text appears in a separate green **Doctor’s assessment · published** panel with notes, follow-up and date. Appointment-linked reviews also appear in My visits → appointment details. Review notifications open the associated assessment using the existing route. A draft stays private and sends no notification. Revoking access prevents future doctor access while retaining published review history for the patient.

For the prepared fictional demonstration: Ava → Skin check → assessment `35188a10` (18 October,7:49pm). Dr. Lim’s independent assessment says: “Fictional demonstration: unable to confirm a condition from this photo alone.” Notes and follow-up are also explicitly fictional. This uses an existing public dataset example, not a real doctor diagnosis. The AI remains Psoriasis83.4% for this source-labelled eczema example; neither its scores nor its stored model version were overwritten.

Reload Expo Go or the browser to obtain the updated panel. The live browser retained its old bundle until reload; after reload the new panel and saved assessment appeared correctly.

## Data and access

Nullable/empty-history compatibility is implemented with `doctor_assessment TEXT NOT NULL DEFAULT ''` added to published reviews and private drafts. Existing notes, follow-up, IDs and timestamps are preserved. Historical reviews with an empty assessment show “No separate assessment was recorded”; no diagnosis is inferred from their notes or AI. New API publication requires a nonblank assessment (maximum500), plus the existing nonblank notes and follow-up. Drafts may remain incomplete. Doctor access, patient ownership, revocation, publication transactions and private-draft boundaries are unchanged.

No new disease training, model selection, class mapping, score threshold, doctor-matching policy, medication, payment, login or Word-report change was made. The user's earlier request to revert the unconfirmed-result presentation remains respected; the experimental AI display is unchanged.

## Verification

98 API tests passed, including three new assessment tests covering private draft/version updates, publication/retry/immutable AI snapshot, access/revocation, validation and legacy migration. Both TypeScript checks, Android export and dashboard production build passed. Browser flow passed: share public dataset record, independently enter fictional assessment, save private draft (not visible to patient), confirm publication, reload patient bundle, view separate panel and switch to Noah to verify Ava's review is hidden. No actual clinical assessment was performed.

Android new-panel/reopening/patient-separation confirmation is pending the user's test-card reply.
