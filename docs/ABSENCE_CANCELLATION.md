# Cancelling future doctor absences

Implemented 19 October 2026. Staff: Doctor schedules -> choose doctor -> Saved dates and cancellation history -> Cancel absence -> review -> Confirm absence cancellation. Keep absence exits confirmation without a mutation. The doctor sees Absence cancelled and its timestamp in their own weekly history, alongside current slot availability.

Cancellation is allowed only before the absence date starts in Malaysia time. The original absence ID, doctor, date, reason, request key and creation time remain stored; only nullable `cancelled_at` is added. Staff can view retained past/cancelled records as well as upcoming dates. There is no hard delete, retrospective cancellation, reason/date editing or automatic patient notification in this increment.

Availability:

- Only active absences block public availability, bookings, rescheduling, slot creation and seeding. Cancelling an absence restores eligibility of existing future open slots, subject to capacity and any other overlapping active absence.
- Manually closed slots stay closed. No slot, booking, prescription, bill, share or weekly pattern is modified or created. A date without slots still requires staff to create/generate times explicitly.
- Overnight slots remain blocked if a second active absence overlaps them, even after the first absence is cancelled. Midnight uses the same half-open Malaysia day rules as full-day absence creation.
- Cancellation invalidates an older weekly preview if skipped times become eligible; staff must preview again. Saved generation retry results remain historical and do not generate previously skipped slots automatically.

Persistence and retries: staff-only POST `/staff/schedules/{doctor_id}/unavailability/{absence_id}/cancel` validates the absence belongs to the selected doctor. A serialized transaction sets one cancellation timestamp. Repeated/concurrent cancellation of the same ID returns its saved result, including a retry after the date starts. Old retries cannot cancel a newer replacement absence. Reusing the original creation request returns the cancelled history, never reactivates it. A new absence for the same date uses a new ID/request and normal booked-date checks.

Migration rebuilds the old absence table within a transaction, preserving every ID/request/source value, and replaces permanent doctor/date uniqueness with a unique index on active records. The new nullable cancellation column preserves old records as active. No other table references absence IDs. Staff and the assigned doctor retain reason access; patient endpoints never expose absence history/reasons. Demo identity headers remain unchanged; real auth is deferred.

Verification:144 API tests passed (seven new cases), dashboard and mobile TypeScript checks and dashboard production build passed. Tests cover restoring open versus closed slots, original pattern/booking preservation, role/doctor scope, Malaysia midnight and retries, re-adding a date, adjacent-day overlap, stale weekly previews, concurrency and legacy schema preservation/reuse. Mobile UI unchanged; no new Android export needed.

Browser: Keep absence preserved the active11November test record, then explicit confirmation cancelled it. Staff history retained the date/reason/timestamp after reload; Lim's read-only week9November shows Absence cancelled and the original11November noon slot with2/2 capacity. Patient booking now offers/selects that slot; Back was used, so no new booking was created. Ava's2November14:00 booking remains visible to Ava and hidden from Noah. API snapshots confirm original slot fields and user-modified weekly patterns are unchanged; absence reason is absent from public availability.

Only our synthetic absence `96c9a23a-a8e0-4f9f-91b9-55e178fb345f` was cancelled, restoring existing slot `3d4a3d04-d804-4f92-9fea-89b105d57c8e`. Evidence: `tmp/absence-cancellation-fixture.json`, `tmp/absence-cancellation-verified.png`. Android restored-time/existing-booking/separation card is pending; no physical result claimed yet.

Services: verified API restarted session32500 PID107152/8000. Prior dashboard/Expo had stopped, ports were checked free, and both restarted: dashboard session39799 PID78988/3000; Expo session91608 PID99028/8081, phone API `http://192.168.0.2:8000`. Expo's cold web bundle completed. These supersede older runtime IDs. AI/model/training, Word, real auth, dependencies and user's `docs/ai/BASELINE_SETUP.md` edit remain unchanged. No push/deploy/main merge.
