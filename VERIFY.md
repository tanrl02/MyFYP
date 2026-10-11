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
