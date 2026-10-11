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
