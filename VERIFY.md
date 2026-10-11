# Verification

Booking/queue increment, 11 October 2026. Starting commit 87ad49d; final checkpoint in Show Log.

Agent checks: six Python API tests passed (persistence, scoping, role rejection, retries, duplicates, concurrent capacity, cancellation/history, transitions, past slots). Both TypeScript checks passed. Build/browser results added below after verification. Physical Android NOT verified. Demo headers are NOT real authentication.

## Phone checklist

Run the three launchers in SETUP.md; synthetic records only:

1. Ava Demo -> Book a visit -> select available doctor/time -> confirm. My visits shows Waiting and token.
2. Dashboard select same doctor/date. Booking appears within a few seconds.
3. Call next patient: phone shows Called. Complete visit: phone shows Completed. Refresh/reopen/restart API: record remains.
4. Noah Demo: Ava records must not appear. Book/cancel a Waiting visit; both screens show Cancelled and availability increases.
5. Full/already booked slots must not produce duplicates. Called/completed visits cannot cancel; only called visits complete, one patient called at a time.
6. Stop API and refresh: connection error. Restart/retry: recovered. If a save times out, refresh visits before choosing a new request.

Future clinic dates may be rehearsed. Camera/AI/prescriptions/billing/login not implemented yet; their checks accompany later increments.

## TortoiseGit

MyFYP -> right-click -> TortoiseGit -> Show Log. Compare starting commit 87ad49d against booking/queue checkpoint to review the entire change. Check for Modifications shows unsaved Git edits. A clean folder proves commits, not functionality. Commit is local; Push uploads and was not performed. Do not discard changes switching branches. SQLite data/dependencies/build files are ignored; Git cannot restore them.

Problem report: screen, steps, expected/actual and visible error; screenshots with synthetic data only.

## Completed agent verification

Next.js production build passed. Expo Android Hermes bundle export passed (JavaScript bundle, NOT APK/device verification). Expo web build ran successfully. Browser interactions verified booking/confirmation, shared staff row, Called and Completed reflected in patient UI, second-patient empty history, cancellation reflected in both screens, and reload retaining saved state/availability. Synthetic Ava L001 completed and Noah L002 cancelled remain in the local demo store. Screenshot under ignored tmp/booking-queue-dashboard.png. Backend persistence after reopening is covered by tests; physical Android and LAN/firewall configuration remain unverified.

## Prescription and billing checks

Starting commit 15ab6e3, feature branch feat/prescriptions-billing. Code implemented; ten backend tests, TypeScript checks, Next build and Android bundle export passed. New browser interactions and physical Android remain PENDING because permissions to inspect processes and start an isolated test dashboard were declined. Do not confuse the previous booking-only browser checks with this increment.

Close your old project service windows and reopen the three launchers in SETUP.md so the new Python endpoints load. No saved records need resetting. Dashboard queue -> Open prescriptions & billing:

1. Book/call Ava with Dr. Lim. Choose Dr. Lim on care dashboard. Create prescription, quantity 2 of Demo item A, leave the sample directions and issue. Ava Care & bills should show Issued, same items/directions. Dr. Anita must not see this visit.
2. Switch to Staff Demo. Confirm dispensing. Status becomes Dispensed on both interfaces; repeat requests must not deduct stock twice. Insufficient stock must leave all items/stock unchanged.
3. Complete the visit on queue screen. Staff generates bill; quantity 2 item A plus demo consultation totals RM 40.00. Repeated generate requests return the same bill. Called/waiting/cancelled visits cannot be billed.
4. Ava Care & bills -> Simulate payment -> Confirm simulated payment. Both interfaces show Paid · simulation, with saved receipt reference. No external checkout/bank/money transfer. Staff may also record the same simulation; repeat requests must not create extra payments.
5. Noah Care & bills must not show Ava's records. Reload/restart API; saved prescription, stock, bill and receipt remain.
6. Test no items, fractional/negative/out-of-range quantity, missing directions, wrong doctor, unavailable stock and API unavailable. Error should prevent invalid saved records and allow recovery.

Fixed demo items: A RM 5.00, B RM 8.00; initial stock 20 each; consultation RM 30.00. These are sample numbers. Issued items are immutable, and a billed visit cannot receive a new prescription. Editing/voiding/refunds, stock batches/restocking and real auth/payments remain final-scope work.

## Verification update — 12 October 2026

Latest result supersedes the pending browser status above. User authorised service restart/checks. API launcher (8000), dashboard launcher (3000), Expo LAN launcher (8081) started successfully. Browser verified empty-prescription validation, Dr. Lim prescription issuing on synthetic L001/Ava, assigned-doctor filtering (Anita cannot see L001), shared patient prescription, RM40 itemised invoice, payment blocked before dispensing, staff dispensing, patient confirmation of simulated payment, saved receipt d9a8efec, dashboard reload persistence and Noah not seeing Ava care data. Screenshot tmp/care-browser-verified.png. Sample stock A reduced from 20 to 18; receipt/bill remain in local ignored database.

Physical Android USER-CONFIRMED: Expo Go opens through LAN; Ava Care & bills shows dispensed prescription and RM40 Paid · simulation; closing/reopening retains records; switching Noah hides Ava's prescription/bill. This confirms those specific checks only. Fresh booking/cancellation/call-next/complete interactions on physical phone and camera tests are not yet confirmed. No secure-auth, real-payment or clinical-reliability claim.

Services left running for continued use: API exec session 54295 (server PID55196), dashboard 97093, Expo 65885. Phone URL exp://192.168.0.4:8081, API http://192.168.0.4:8000. LAN address can change on another network. Restart through SETUP launchers if services later stop. No network security/firewall settings changed.

## Skin assessment checks — 12 October 2026

Start13dee42, feature branch feat/skin-assessment. Thirteen backend tests passed: photo format/size/dimension validation, resizing, EXIF/text metadata removal, atomic saving/reopening, request retry/hash mismatch and patient/role scoping, plus existing booking/care tests. Both TypeScript checks passed. Browser synthetic image (tmp/assessment-demo.png) select/preview/save, simulation labels, reload history/open saved photo and Noah separation passed. Screenshot tmp/assessment-browser-verified.png. LAN API health verified. Android export passed; camera/gallery/device confirmation tracked below.

Phone checklist: Skin check -> Take photo of harmless object -> grant camera -> preview -> save; result must say SIMULATION, no analysis/diagnosis. Choose photo -> select non-sensitive image -> preview; cancel a new selection and previous preview must remain; discard must not add history. Close/reopen app -> Refresh history -> open saved photo; Noah must not see Ava history. Deny camera -> helpful recovery/gallery option; if permanently denied Open app settings available. Oversize/unsupported/corrupt file must not save. Server restart retains saved images; no real inference/private hosted access tested.

Supported JPEG/PNG/WebP <=5MB, minimum32px per side, <=25MP. Normalized saved photo <=1600px longest side with source metadata removed. Latest100 history entries shown. Source filename discarded. Original resolution/source metadata not retained. All identities remain simulated/spoofable: synthetic/non-sensitive photos only. No external AI calls; no pretrained/fine-tuned model yet.
## Android upload correction — 12 October 2026

User reported camera/preview working but saving failed with `Unsupported FormDataPart implementation`. Expo SDK 57's installed multipart converter explicitly rejects legacy `{uri, type, name}` parts. Native upload now appends the cached expo-file-system File directly, which the converter reads through its bytes interface. The preview remains available on failed saves. Mobile TypeScript and updated Android Hermes export passed. User explicitly confirmed retry now saves the photo and SIMULATION result on Android. User also confirmed gallery saving, closing/reopening and opening Ava's saved history/photo, and Noah cannot see Ava's assessments. Camera permission-denial recovery and picker cancellation/discard remain manual checks not yet confirmed.
## Doctor sharing and review — 12 October 2026

Started from 443cd41 on feat/doctor-review. Patient opens a saved assessment -> chooses doctor and optional fictional message -> confirms sharing. Only that assessment is shared. Doctor opens /reviews, selects the assigned demo identity, opens the inbox entry and confirms publication of a required note/follow-up. Patient sees the published review in that assessment's history. Revoke confirmation removes future doctor access; patient retains published reviews. Fresh sharing after revocation creates a new grant. A delayed retry of the old request does not reactivate access. Published reviews cannot be replaced in this increment.

Seventeen backend tests passed, including own-patient/assigned-doctor/role denial, retry/content conflicts, independent doctor grants, revoked detail/publication rejection, retained patient reviews, reopening persistence, input limits and concurrent consent/publication/revocation. Both TypeScript checks, Next production build and Android Hermes export passed.

Browser verified confirmation, synthetic assessment c5487b2f shared with Lim (share3c81e31c), photo/message/simulation display, publication, patient review visibility, Anita isolation, revoke confirmation, open doctor detail/photo cleared by five-second polling, patient revoked history/review retained after reload. Screenshot tmp/doctor-review-verified.png shows agent's synthetic image and fictional review. Other user-created shares were left untouched. User explicitly confirmed Android sharing, published review visibility after reopening and Noah cannot see Ava's sharing/review history. Physical Android revocation not yet separately confirmed. Existing booking/care/skin checks remain applicable.

Limits: identities are spoofable demo headers, real login/register deferred by user until later. No clinical reliability, hosted storage or real inference claim. Staff cannot access these endpoints. Bookings do not automatically expose a patient's entire photo history. Inbox/patient sharing history limited to latest100 grants; unsaved review drafts stay only in screen memory. Revocation cannot recall already viewed information. Model inference, consultation-linked authorization, review amendments, record retention policy and remaining nine-module operations still required. Word unchanged.
## Small increment: appointment assessment link — 12 October 2026

From7d65e62, feat/appointment-assessment-link. Patient opens a saved assessment -> Link to appointment -> chooses own future waiting/called visit -> confirms. Assigned doctor derived by backend; one active assessment link per appointment. Patient sharing history and doctor inbox/detail show queue token/date/status. Explicit direct shares remain separate. Revoke removes link access; appointment cancellation atomically revokes only its grant. Completed visits retain previously authorized links/reviews, but cannot receive new links. Revoked history/reviews retained; replacement needs a fresh confirmation/request.

21 backend tests passed, including ownership/doctor/role denial, retry/mismatch/duplicate prevention, cancellation without touching direct shares, completed-visit rules, replacement, reopen persistence and migrating existing direct shares/reviews. Both TypeScript checks, Next production build and Android export passed. Browser verified empty eligible list, booked synthetic Ava/L003, link confirmation for synthetic assessment c5487b2f (grant90ca94ec), saved disabled duplicate control, assigned doctor photo/appointment display, Anita isolation and patient reload persistence. Screenshot tmp/appointment-link-verified.png contains only synthetic image. User confirmed Android linking control shows L003 and saved link remains after closing/reopening. New link creation/cancellation on phone not yet confirmed.
## Small increment: consultation notes — 12 October 2026

From60e34c5, feat/consultation-notes. Doctor /consultations lists assigned called/completed visits and opens active appointment-linked assessment/photo only when patient grant remains active. Findings (max2000) and follow-up (max1000) required; confirmation publishes one fixed note per called visit. Exact retries return existing note; changed content conflicts. Patient My visits displays own published notes. Staff and other patients/doctors denied; operational /care stays free of consultation text. Published note remains after completion and after assessment consent revocation. Initial publication after completion denied; saved exact retry remains valid. Drafts stay only in screen memory; amendments deferred.

25 backend tests, both TypeScript checks, Next production build and Android Hermes export passed. Browser called synthetic Ava/L003, opened linked synthetic photo, checked empty-input disabled publication, confirmed fictional findings/follow-up, verified patient My visits, reload retention, Noah hiding Ava's note, Anita filtering, and note retained after completing L003. Screenshot tmp/consultation-note-verified.png. Other user-created visits untouched. User confirmed Android Ava/L003 findings and follow-up display, retention after reopening and Noah not seeing Ava consultation notes. API20272 PID60148, dashboard97093, Expo21814. No new dependencies, real AI/auth or Word edits.

## Small increment: staff counter booking — 12 October 2026

Staff dashboard Patient queue -> New counter booking -> Ava/Noah, doctor, available time -> Review counter booking -> Confirm counter booking. A successful booking selects its doctor/date in the queue and produces the same queue token seen under patient My visits. Only staff can call POST /counter-bookings. Reuse of the same patient/request returns the existing booking; changed slot conflicts. New requests for an already booked active patient/slot conflict. Full slots are rejected atomically even if availability changed after confirmation. Patient cancellation restores capacity through the existing flow.

28 backend tests passed (staff attribution, patient separation, persistence, input/role denial, duplicate/capacity prevention and concurrent phone/counter retries included). Both TypeScript checks and dashboard production build passed. Browser created synthetic Ava/L004, Dr Lim, 12 October 11am; Waiting appears in shared queue and Ava My visits after reload. Noah has no L004. Repeated submission with a fresh request shows duplicate error and retains one queue row. Screenshot tmp/counter-booking.png. Physical Android shared-record/reopening check pending. Mobile UI unchanged; no Android export rerun. All previous applicable feature checks remain valid; this is not complete final-module acceptance.

12 October Android confirmation: user reopened Smart Skin and confirmed Ava My visits shows L004 while Noah does not. The shared-record/reopening/patient-separation phone check passed. Counter booking checkpoint 76c8287 is on local main; no push. Previous pending Android status is superseded by this confirmation.


## Small increment: appointment rescheduling — 12 October 2026

Patient My visits -> Reschedule [token] -> choose time -> Confirm. Staff Patient queue -> Reschedule [token] -> select time -> Review -> Confirm. Original waiting booking stays intact on failure; successful move retains old history as Rescheduled and creates a new queue number. Server rejects other-patient/doctor access, non-waiting or started original/target, same slot, duplicate active patient/slot and full capacity. Retry uses the same request key; mismatched reuse conflicts. Same-doctor active appointment grant follows the replacement; changing doctors revokes only appointment grants and requires fresh patient linking. Direct grants remain active.

32 API tests passed, including ownership/status/input denial, original preservation, SQLite reopen, request retry/event-once, shared history, same/change-doctor consent and concurrent phone/counter capacity. Both TypeScript checks, dashboard production build and Android Hermes export passed. Browser staff moved own synthetic L004 -> Lim/L00113Oct9am, patient -> Anita/A00114Oct9am; verified new shared queue, old Rescheduled history, reload retention and Noah separation. Screenshot tmp/reschedule-verified.png. Android creation/reopening/separation card pending. Other user visits untouched. Full nine-module final acceptance remains incomplete.

Android check is unresolved: user selected 'Something is wrong; I will describe it'. A follow-up card asks for the failing step and exact error. Do not claim physical rescheduling passed. Implementation cdeeb66 is on local main; automated/browser checks passed. Diagnose the user's description before starting another function.


Android development-server recovery: user reported Metro could not resolve ./RescheduleView from App.tsx. Verified RescheduleView.tsx exists on main. Stopped owned Expo21814 and restarted with --clear --lan; current Expo session91250 port8081. Fresh Android development bundle /apps/mobile/index.bundle compiled successfully (HTTP200,4435971bytes). No source/dependency change needed. Phone retry confirmation pending. API31268 PID67616 and dashboard97093 unchanged. Avoid temporary removal of imported files while Metro runs during future Git recovery operations.


12 October phone recovery confirmation: after the Expo cache restart, user replied 'ok already', confirming the reported missing-RescheduleView error is resolved. Rescheduling implementation and automated/browser verification are complete. Do not infer separate Android reopening/patient-isolation results beyond this brief confirmation; browser persistence/isolation were verified. Expo91250, API31268 PID67616 and dashboard97093 remain the latest owned services. Discuss the next small function with the user before starting it.


## Small increment: visit feedback — 12 October 2026

Patient My visits -> Visit feedback -> Give feedback [completed token/date] -> rate1-5 -> optional fictional comment(max1000) -> Review -> Confirm. Review disabled without rating. Confirmation locks fields and explains staff visibility/fixed publication. Saved feedback replaces submission button. Staff Patient queue footer -> Visit feedback (/feedback) shows latest100 submissions and average across displayed submissions, polled5seconds. Patients view only own records. No raw consultation notes/photos returned. Doctor read and non-patient submission denied.

35 API tests passed including eligibility/roles/ownership, strict ratings(no bool/string/fraction/out-of-range), comment limit, immutable retry/conflicts, event-once, concurrent duplicate prevention and database reopening. Both TypeScript checks, Next production build and Android Hermes export passed; live Android development bundle HTTP200. Browser Ava/L0034-of-5 fictional comment, staff visibility/average4.0, patient reload retention, removed duplicate-submit control, Noah separation passed. Screenshot tmp/feedback-verified.png. Physical Android submission/reopening/isolation pending. Draft comments remain only in screen state; leaving/remounting clears them. Latest100 per identity; amendments/moderation/pagination are outside this increment. Demo identities remain spoofable. Word unchanged.

12 October Android feedback verification: user explicitly confirmed submitting rating/comment, reopening persistence and Noah not seeing Ava feedback. Phone check passed; earlier pending feedback status superseded. Increment6a71290 ready for local main. All nine final modules remain required; Word/auth still deferred.


## Small increment: stock receiving — 12 October 2026

Staff Prescriptions & billing -> Demo role Staff -> Stock -> select item, whole quantity1-1000, fictional requiredreason(max300) -> Review -> Confirm. Invalid/empty fields disable Review; confirmation locks values, Keep editing/Cancel available. Saved receipt is fixed with before/after snapshots; current balances poll5sec and may differ after later operations. Low stock<=5, outofstock0; latest100 receiving history. Read/write endpoints /stock and /stock/receive restricted to staff. Failed saves preserve stock; same request/content retry adds only once; changed reuse conflicts. Total demo stock cap100000.

38 API tests, both TypeScript checks and dashboard build passed. Browser navigated staff Stock, checkedzero quantity disabled, confirmed fictional receipt f04b598c for demo-a+3 (17->20), verified card/history and reload retention. Screenshot tmp/stock-verified.png. Low-stock branch supported by isolated low-stock fixture/threshold; no production low-stock display claim or depletion. Existing dispense-once/insufficient-stock and new concurrent receiving/dispensing checks passed. Mobile source unchanged; no physical Android action required. No new dependencies, real medication/prices/payment or Word changes. Receiving history does not include dispensing events; those remain existing booking events.

## Small increment: patient appointment details — 12 October 2026

Patient My visits -> tap appointment summary/View visit details. Sections show appointment/status, linked simulation assessment and published doctor review/follow-up, consultation findings/follow-up, issued/dispensed prescription, itemised invoice/paid simulation receipt, submitted feedback. Empty records are explained. Back returns to visits. Rescheduled visit offers its replacement details. Patient/tab changes clear selection and scrolltop; details poll5sec/onforeground. Error clears stale details and offers Retry. Read-only screen, no photo BLOB fetch or new consent/payment action.

41 API tests passed: full saved bundle/reopen, otherpatient404, staff/doctor403, missing404, empty sections, direct-share exclusion, retained review afterrevocation and rescheduled replacement/link scope. Both TypeScript checks and final Android Hermes export passed. API test auto-review timed out once; allowed single retry passed. Browser verified L003 syntheticlinkedassessment/consultation/prescription/feedback, live appearance of fictional review published for existing synthetic grant90ca94ec, Back, L00112Oct9am dispensed/RM40paid simulation, patient-switch isolation and L004->replacement. Screenshot tmp/visit-details-verified.png. Physical Android opening/back/reopen/isolation pending. Only latest100 linked grants returned pervisit; direct reviews remain in Skin check. Existing user's issued20/20 prescription not modified/dispensed.

12 October Android appointment-details verification: user explicitly confirmed opening L003 linked assessment/published review/consultation, Back, L001 dispensed prescription/RM40 paid simulation bill, reopening details and Noah isolation. Physical check passed; earlier pending status superseded. Implementationa012648 ready for local main. Word/auth still deferred; discuss next manageable function.


## Small increment: daily clinic report — 12 October 2026

Staff Patient queue footer -> Daily reports -> date -> View report. Current summary polls10seconds. Dates use Malaysia UTC+8. Visits are selected appointment-date booking records by current status; rescheduled original separate from cancelled. Billing for that appointment cohort uses current paid/unpaid status (not collection-date cashflow). Stock uses receiving/dispensing timestamp day; feedback uses submission day. Quantities represent movement, not ending balance. Explicit labels, empty0/nullaverage and Retry; no patient/clinical details returned.

44 API tests passed including mixed invoicing/visits/reschedules totals, aggregation without join double-count, staff-only/invalid-date denial, emptydate, reopen, no clinical fields and exact Malaysia midnight inclusion/exclusion. Both TypeScript checks and final dashboard production build passed. Browser queue navigation,12Oct totals,2000-01-01 zero/empty report and explicit return12Oct passed. Screenshot tmp/daily-report-verified.png. No production mutations. Mobile unchanged, no Android export/phone check required. Exporting/charts/date-range/adminaccess remain future tasks. This is a current report snapshot, not frozen day-end history.


## Patient medical background (12 October)
Automated:47 API tests, both TypeScript checks, dashboard build and Android Hermes export passed. Browser save/review/reload and patient/doctor switching verified; physical Android pending.
1. Android Ava -> My profile -> enter fictional allergies, medicines and conditions -> Review background -> Confirm background.
2. Reopen app -> Ava -> My profile: saved values remain. Noah must not see Ava's values.
3. Doctor dashboard /consultations -> Dr Lim -> L003: Patient background shows the latest Ava values and timestamp; published notes stay unchanged.
4. Empty fields show Not provided. Staff and other patients cannot access Ava background. Unassigned doctor/uncalled visit rejects detail. Concurrent stale edits return conflict and require explicit reload, while identical save retries are safe.

