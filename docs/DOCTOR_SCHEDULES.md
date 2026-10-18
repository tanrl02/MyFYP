# Staff-managed weekly doctor schedules

Implemented 18 October 2026. User chose staff management; doctors have read-only access to their own schedule. Open dashboard -> Doctor schedules (`/schedules`), also linked from Individual appointment slots and Consultation notes.

Staff flow:

1. Select Staff Demo and the doctor. Choose working weekdays, one shared same-day session start/end, slot duration15–120 minutes in15-minute steps, and capacity1–20 per slot. Review and confirm the weekly pattern.
2. Choose a future Monday within eight weeks. Preview the dated week, including every proposed slot and capacity. Confirm the week to publish its new times into existing patient booking/rescheduling screens. At most200 slots per week; sessions must divide into whole slots. This increment supports one shared session per selected day; multiple sessions/breaks, leave/holiday exceptions, and editing booked slots remain separate work.
3. Saving a pattern alone creates no dated slots. Generate each week explicitly; there is no background scheduler. Later pattern changes apply only to subsequent explicit generation and never move, cancel or erase existing slots/bookings.

Doctor flow: select the doctor's demo role and a Monday. The page shows the staff-saved pattern and actual dated slots for that week, remaining capacity, queue tokens, patient display names and visit statuses. The API derives the doctor from the actor; no other-doctor lookup is accepted. No clinical notes, background, photos, reasons, prescriptions, billing or patient IDs are returned by this operational view. It does not expand clinical-record access. Demo headers remain selectable identities, not real authentication.

Patient flow: Book a visit -> choose any generated open time -> confirm normally. Existing ownership, capacity, retries, queue ordering, cancellations, rescheduling and consent rules are reused. Patients cannot read or change the weekly pattern endpoints. Generated availability is shared publicly like existing appointment slots; each patient's bookings remain private.

Safety and persistence:

- New `doctor_schedule_patterns` table stores one current pattern/version per doctor and staff save timestamp. Changed saves require the current version; same-content retry is safe. Reload saved pattern explicitly replaces unsaved edits.
- New `schedule_generations` table records request identity, doctor/week/pattern version, preview fingerprint and saved result. No rewriting of existing slots/bookings or dependency change.
- Preview is read-only. Exact open slots with the same duration/capacity are retained, including booked slots. Closed exact starts, differing details, or overlap with another open slot cause conflicts. Touching endpoints are allowed; overlaps from a previous day's overnight slot are detected.
- Any conflict blocks the entire batch. Confirmation rereads the pattern/slot plan in `BEGIN IMMEDIATE` and requires the preview fingerprint to match. An intervening booking in an already-retained slot does not invalidate the plan. New/closed/changed slots require another preview. Concurrent manual slot creation or generation cannot interleave partial batches.
- Exact generation retries return the saved result, even after time/pattern changes, and cannot create duplicate slots. Changed request reuse conflicts. Failure during creation rolls back every new slot and the generation record. A repeat preview reports existing matching slots as retained.
- Once a doctor has a saved weekly pattern, startup stops adding new automatic demo seed slots for that doctor. Previously saved seed slots, manual slots and bookings remain unchanged and visible. The other doctor's demo seeding is unchanged until staff saves their pattern. Existing individual-slot closure rules remain available.

Verification:129 API tests passed (10 new schedule cases), dashboard and mobile TypeScript checks and dashboard production build passed. Mobile screens are unchanged; no new Android export was required. Tests cover role/input/date bounds, version conflicts, restart/retry, preview read-only behaviour, retained bookings, patient booking, closed/different/overlapping slots, atomic rollback, concurrent manual creation/generation, doctor separation/minimal payloads, and seed preservation.

Browser: staff saved DrLim Monday/Wednesday14:00–15:00,30-minute slots, capacity2, version1. Generated week2November2026 with four new slots (2 and4November,14:00 and14:30); repeat preview shows0new/4retained. Ava booked2November14:00 (L001 Waiting), which appears in Lim's read-only schedule with1/2 places available. Anita's same-week view is empty. Saved pattern/booking survived reload; Noah has no Ava booking. Existing user slots/visits unchanged. Evidence: `tmp/weekly-schedule-fixture.json`, `tmp/staff-weekly-schedule-preview.png`, `tmp/doctor-weekly-schedule.png`.

Android: user replied "Yes, generated times, reopening and separation work", confirming generated2/4November times, Ava L0012November14:00 after reopening and Noah isolation. No physical leave/holiday/closure checks are claimed.

Runtime: API session14517 PID16004 port8000 using `.venv-ai`; existing dashboard17348/3000 and Expo28048/8081 retained. AI/model/training, real auth, Word, dependencies and user's `docs/ai/BASELINE_SETUP.md` edit preserved. No push/deploy/main merge. Discuss the next manageable improvement before implementation.
