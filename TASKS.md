# Tasks

Updated 11 October 2026. Increment starts from 87ad49d.

| Task | Status | Evidence / remaining work |
| --- | --- | --- |
| Scope/design/access | Approved | Nine final modules, five preview workflows, one Python backend |
| Initial report review | Partial coverage complete | Remaining review in docs/REPORT_REVIEW.md |
| Word alignment | Deferred by user | Original unchanged; revisit after implementation |
| Shared booking/queue | Implemented; checks in VERIFY.md | SQLite/API, mobile and dashboard; physical Android pending |
| Prescription/dispensing | Implemented; browser and specified phone checks passed | Assigned-doctor issue, stock-safe staff dispensing |
| Billing/simulated payment | Implemented; browser and specified phone checks passed | Saved itemised invoices, retry-safe simulation |
| Skin photo/history/simulated AI | Implemented; browser and specified Android checks passed | Camera/gallery saving, reopening, own history |
| Real auth/private storage | Pending | No Supabase environment selected/accessed |
| Doctor sharing/review | Implemented; browser/automated and specified Android checks passed | Explicit per-assessment grants, publication and revocation |
| Dataset/model/fine-tuning | Pending | Common conditions, exact classes/licences unresolved |
| Remaining final modules | Required | Accounts/OCR, users, medical records, full pharmacy, feedback/reports and remaining workflow details |
| Full preview | Incomplete | Five flows and phone confirmation needed; tentative 22 October |

See TortoiseGit Show Log for local checkpoints. No remote push/publication. Booking/queue completion does not mean the full preview or FYP is finished.

Prescription/billing increment: implemented, automated checks passed; browser/Android verification pending. Doctor issues against assigned called/completed visit, staff dispenses once, completed visit generates frozen invoice, patient/staff records simulated payment. Next skin assessment/photo/history; entire five-flow preview still incomplete. Keep feat/prescriptions-billing until UI checks pass.

12 October 2026: prescription/billing browser checks passed. User-confirmed Android opening, shared paid bill/dispensed prescription, reopening persistence and patient separation. Care increment ready for main; full physical booking/queue and camera still pending. Next implementation: skin assessment/photo/history. Word unchanged.

Skin assessment implemented on feat/skin-assessment: camera/gallery/preview, local-backend photo/history, labelled simulation. Automated/browser checks passed; user confirmed Android camera/gallery saving, reopening and patient separation after native upload correction. All five preview feature groups now have code, but full preview acceptance and final nine-module scope are not complete. Real auth, inference/fine-tuning, doctor review/sharing and remaining full-module operations still required.
12 October user prioritisation: implement feature improvements and doctor sharing/review before real login/register. Real accounts remain required for final scope, scheduled later. Doctor review verified in browser; user confirmed Android sharing, review visibility, reopening and patient separation. Word remains deferred.
12 October small-task rule: user wants one manageable increment at a time, with discussion between tasks. Current increment appointment-assessment linking implemented; automated/browser checks passed, user confirmed Android control/display/reopening persistence. No authorization to batch the larger roadmap into this task.
12 October consultation notes: approved as separate manageable task. Implemented fixed publication on called visit, assigned-doctor consultation workspace/live authorized linked photo, own patient published notes under My visits. 25 tests/builds/browser checks passed; User confirmed Android note display/reopening/patient separation. Corrections/drafts/history expansion remain future separate tasks; login and Word still deferred.

12 October counter booking: implemented staff confirmation flow using existing shared booking rules. 28 API tests, TypeScript and dashboard build passed; browser creation/shared queue/patient visibility/reload/separation/duplicate checks passed. Android confirmation pending. Full patient registration, rescheduling and real authentication remain separate tasks. Word unchanged.

12 October Android confirmation: user reopened Smart Skin and confirmed Ava My visits shows L004 while Noah does not. The shared-record/reopening/patient-separation phone check passed. Counter booking checkpoint 76c8287 is on local main; no push. Previous pending Android status is superseded by this confirmation.


12 October rescheduling: patient/staff confirmation flow implemented for future waiting visits, with shared new queue number/history, atomic capacity/duplicate protection and doctor-change appointment-grant revocation. 32 tests, TypeScript, dashboard build, Android export and browser staff/patient flows passed. Android creation/reopening/isolation confirmation pending. Real login and Word remain deferred.

12 October phone recovery confirmation: after the Expo cache restart, user replied 'ok already', confirming the reported missing-RescheduleView error is resolved. Rescheduling implementation and automated/browser verification are complete. Do not infer separate Android reopening/patient-isolation results beyond this brief confirmation; browser persistence/isolation were verified. Expo91250, API31268 PID67616 and dashboard97093 remain the latest owned services. Discuss the next small function with the user before starting it.


12 October visit feedback: own completed-visit rating/comment submission with confirmation, saved history and staff feedback tab implemented. One immutable submission per visit; editing/moderation/replies/reporting expansion deferred.35 API tests, TypeScript, dashboard build, Android export/development bundle and browser submission/persistence/separation passed. Android confirmation pending. This completes a first feedback function, not all final reporting/module requirements.

12 October Android feedback verification: user explicitly confirmed submitting rating/comment, reopening persistence and Noah not seeing Ava feedback. Phone check passed; earlier pending feedback status superseded. Increment6a71290 ready for local main. All nine final modules remain required; Word/auth still deferred.

