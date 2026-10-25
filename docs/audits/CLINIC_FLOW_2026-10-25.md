# Clinic visit workflow audit — 25 October 2026

The complete API rehearsal passed using the existing staff-only completion step. One workflow handover gap was identified: there is no explicit doctor-finished signal for staff.

This is an audit result, not an implementation change. The permission rejection described below is current intentional role enforcement, not a failed security check.

## Scope and isolation

- Normal saved database backed up to `tmp/before-clinic-flow-audit.sqlite3`; all workflow writes went to `tmp/clinic-flow-audit.sqlite3`.
- Real API routes exercised through FastAPI TestClient against that copy. No running API, dashboard or Expo process was changed.
- Reused Ava’s existing experimental assessment `90ee5393`, including its saved photo, prediction and patient-reported symptoms. Photo capture/upload and fresh AI inference were not rerun; no model or training changes.
- New fictional appointment used a free Dr Lim session on **4 November 2026 at 2 pm**. No real appointment or payment was created. The rehearsal advances a demo appointment through its lifecycle; it is not a physical visit/date-policy or Android UI acceptance test.

## Results

| Handover/check | Observed result |
| --- | --- |
| Patient assessment and explicit consent | Saved experimental assessment reopened with symptoms; new appointment link granted only its assigned doctor access. Booking/link retries kept the same records. |
| Staff queue | Correct patient changed from Waiting to Called. Calling another patient while this visit was active was rejected. |
| Doctor clinical context | Assigned doctor received the linked photo, saved AI result, patient symptoms and current patient-provided background. Other doctor and staff clinical-detail requests were rejected. |
| Doctor documentation | Separate fictional photo review and consultation note published; prescription issued. Repeated note/prescription submissions returned the existing records. |
| Doctor → staff completion | **Gap F1:** doctor completion request returned 403; after publishing note/prescription the staff queue still showed Called, without a consultation-finished/ready-for-checkout field. Staff manually completed the visit to continue. |
| Dispensing | Two units of demo-a deducted once: **21 → 19**. Repeating dispensing did not deduct again. |
| Invoice and simulated payment | One itemised **RM40.00** invoice. Repeated invoice creation/payment returned the saved result; one payment event. Noah could not pay Ava’s invoice. |
| Patient follow-up | Feedback saved, visit details contained linked review, consultation, dispensed prescription and paid simulation bill. Reopening retained the result. Noah’s bookings, care and feedback lists excluded the audit visit. |
| Reports | Appointment-date report gained one completed visit and RM40.00 billed/paid. Actual activity-day report gained two dispensed units and one feedback submission. These deliberately use different date bases: 4 November appointment cohort, 25 October dispensing/feedback activity. |

All audit visit event types occurred exactly once, including retried operations. Raw assertions/results: `tmp/run_clinic_flow_audit.py`, `tmp/clinic-flow-audit.log`, `tmp/clinic-flow-audit-result.json`.

## F1 — Missing explicit doctor-to-staff completion handover

**Priority:** next workflow improvement, ahead of additional inbox/filter features.

Current flow requires staff to infer or obtain confirmation that the doctor has finished. Publishing the consultation note and issuing a prescription do not explicitly send the visit to staff checkout. Staff can mark any Called visit completed; no doctor-finished indicator is displayed in the queue.

Evidence:

- `apps/api/app/main.py:383-385`: visit completion route depends on staff identity; assigned doctor receives 403.
- `apps/api/app/store.py:996`: staff completion changes Called to Completed and records an event; no doctor-finished checkpoint.
- `apps/dashboard/app/consultations/page.tsx`: doctor can publish findings but has no Finish consultation/handover action.
- `apps/dashboard/app/page.tsx:50`: staff queue presents Complete visit for a Called row, without a doctor-finished indicator.

Recommended next small increment, **subject to user discussion**:

1. Assigned doctor explicitly marks the consultation finished.
2. Staff sees a clear **Ready for checkout** indicator without access to private clinical notes.
3. Staff retains responsibility for completing the visit, dispensing and billing.

The exact prerequisite for finishing (published note, optional prescription, or another rule) must be agreed before implementation. No completion permissions, statuses or queue behaviour were changed during this audit.

## Preservation and limits

`tmp/check_clinic_flow_audit_data.py` confirms all 34 normal database tables remain unchanged. The unrelated `docs/ai/BASELINE_SETUP.md` modification retains SHA256 `9B298809528CE974274662E63C7C67C88939ED1B8E00AEBD063AD4A63DE19AEA` and is excluded from the audit commit.

This does not replace the user’s deferred physical Android checks. The prior 313 API tests, 35 mobile helper tests, dashboard build/type checks and CSV checks were not rerun because this task changes no application code. No push, deployment, merge, Word report edit or real-authentication work.
