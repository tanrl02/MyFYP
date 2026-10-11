# Tasks

Updated 11 October 2026. Increment starts from 87ad49d.

| Task | Status | Evidence / remaining work |
| --- | --- | --- |
| Scope/design/access | Approved | Nine final modules, five preview workflows, one Python backend |
| Initial report review | Partial coverage complete | Remaining review in docs/REPORT_REVIEW.md |
| Word alignment | Deferred by user | Original unchanged; revisit after implementation |
| Shared booking/queue | Implemented; checks in VERIFY.md | SQLite/API, mobile and dashboard; physical Android pending |
| Prescription/dispensing | Implemented; UI/device checks pending | Assigned-doctor issue, stock-safe staff dispensing |
| Billing/simulated payment | Implemented; UI/device checks pending | Saved itemised invoices, retry-safe simulation |
| Skin photo/history/simulated AI | Pending | Capture/gallery and durable storage |
| Real auth/private storage | Pending | No Supabase environment selected/accessed |
| Dataset/model/fine-tuning | Pending | Common conditions, exact classes/licences unresolved |
| Remaining final modules | Required | Accounts/OCR, users, medical records, full pharmacy, feedback/reports and remaining workflow details |
| Full preview | Incomplete | Five flows and phone confirmation needed; tentative 22 October |

See TortoiseGit Show Log for local checkpoints. No remote push/publication. Booking/queue completion does not mean the full preview or FYP is finished.

Prescription/billing increment: implemented, automated checks passed; browser/Android verification pending. Doctor issues against assigned called/completed visit, staff dispenses once, completed visit generates frozen invoice, patient/staff records simulated payment. Next skin assessment/photo/history; entire five-flow preview still incomplete. Keep feat/prescriptions-billing until UI checks pass.

12 October 2026: prescription/billing browser checks passed. User-confirmed Android opening, shared paid bill/dispensed prescription, reopening persistence and patient separation. Care increment ready for main; full physical booking/queue and camera still pending. Next implementation: skin assessment/photo/history. Word unchanged.
