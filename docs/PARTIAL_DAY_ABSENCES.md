# Partial-day doctor absences

Implemented 19 October 2026. Staff manage absences in Doctor schedules. Choose the doctor and future date, select All day or Time range, enter the private reason, review and confirm. Time range requires both HH:mm values and a later end on the same date, in Malaysia time. Overnight absences can use separate dated periods; this increment does not add overnight time-range entry or editing. Cancellation remains restricted to dates after today, including for partial absences.

Staff and the assigned doctor see exact ranges, reasons and retained cancellation history. Patients see available times only. Cancel absence -> review the exact range -> Confirm absence cancellation retains all original values plus cancellation timestamp. Keep absence makes no change. Cancellation generates no slots or appointments.

Rules:

- Adjacent and separate active periods on one date are allowed. Overlapping active absences are refused, including a full-day absence covering any partial period.
- Intervals include their start and exclude their end. An absence12:00–12:30 blocks a slot starting12:00, leaves one starting12:30 available, and blocks any slot crossing into the period. Slots are never split.
- Any non-cancelled booked slot overlapping the proposed interval blocks saving, even if its start is outside the absence. Waiting, called and completed visits are protected. Visits outside the period are unaffected.
- All existing booking channels, rescheduling, individual slot creation, sample seeding and explicit weekly generation use the interval guard. Weekly preview skips only overlapping slots and becomes stale when eligibility changes. Historical generation retries stay historical.
- Cancelling one period restores existing open slots only if no other active absence overlaps; capacity/manual closure remain enforced. Original bookings, slot fields and weekly patterns remain unchanged.

Storage/API: POST /staff/schedules/{doctor_id}/unavailability accepts optional nullable start_time/end_time. Both null or omitted means All day. API rejects malformed/one-sided/reversed/equal/overnight time ranges. Responses to staff and assigned doctor include both nullable values. Request retries compare date/reason/doctor/times and return retained history; cancelled requests never reactivate. Future cancellation endpoint is unchanged. Serialized transactions prevent overlapping simultaneous creations.

Migration adds nullable times transactionally to previous schemas, preserving full-day active and cancelled records, IDs, dates, reasons, timestamps and request keys. The old active-date unique index is replaced by an active doctor/date lookup index; application transactions enforce interval overlap. The older pre-cancellation table rebuild remains supported and tested.

Verification:152 API tests, including8 new cases, passed; final8 focused cases passed after strict ASCII time validation. Dashboard production build and TypeScript passed. Mobile TypeScript passed with existing Expo globals explicitly loaded: node node_modules/typescript/bin/tsc --noEmit --types expo/types. This checkout has no generated expo-env.d.ts, so plain tsc reports process missing in unchanged apiConfig.ts. No dependency installation, mobile code change or new Android export.

Browser checked staff review/Keep editing/save/reload, booked-period refusal, exact cancellation review/Keep absence, doctor range/reason and blocked versus adjacent slot, patient adjacent selection/Back, Ava existing visit and Noah isolation. Snapshots confirm no original slot-field/booking/pattern mutation. Only new synthetic absence84fc1154-52ab-4d0f-84b4-16b97838724e and adjacent empty12:30 slotcc6b3f4c-de07-4175-8a28-e847d485b49d were created. Original synthetic11November noon slot3d4a3d04-d804-4f92-9fea-89b105d57c8e remains stored and now hidden. Screenshot tmp/partial-day-verified.png was visually inspected; fixture/before snapshots are under tmp/. No new patient booking.

Android confirmed by the user on19October2026: "Yes, partial-day blocking and existing booking work". After reopening, Lim11November noon is hidden,12:30 is selectable and Back works; Ava L0012November14:00 remains unchanged and hidden from Noah. This resolves the pending physical check.

Auth, Word report, experimental AI/model/training, dependencies and user baseline edit unchanged. No push/deploy/merge.

Final runtime: API session98750 PID119452/8000, dashboard PID78988/3000, Expo PID99028/8081. Dashboard TypeScript also passed after restoring the build-generated next-env.d.ts path change.
