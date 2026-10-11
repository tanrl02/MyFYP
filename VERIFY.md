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
