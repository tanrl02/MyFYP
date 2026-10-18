# Editing visit feedback

Implemented 18 October 2026. User approved editing feedback during the first 24 hours after its original submission.

Patient flow: My visits -> Visit feedback -> Edit feedback for the completed visit -> change rating/comment -> Review feedback update -> Confirm feedback update. The form starts with saved values, previews the proposed rating/comment, allows cancellation, and shows the editing deadline in Malaysia time. Saved records and visit details show the original Submitted time and optional Edited time. Older feedback remains visible with a closed-window message.

Staff sees the current rating/comment, Edited timestamp and the recalculated average of the latest 100 submissions. One rating per visit is retained; editing does not increase the count or move the record into another submission-date cohort. Daily reports use the latest rating against the original submission date. Doctor permissions are unchanged: feedback remains patient/staff only. No feedback deletion, replies or moderation was added.

Server rules:

- Additive `visit_feedback.version` (default0) and nullable `edited_at` preserve existing rows. `edit_deadline` is derived from `created_at + 24 hours`.
- Patient-only POST `/visits/{booking_id}/feedback/edit` requires rating1–5, optional comment up to1000 characters, and a strict nonnegative version. Only the owning patient of a completed visit with existing feedback may edit.
- Server time is authoritative. A new edit is rejected at exactly24 hours and later. Device time only controls the displayed action; changing it cannot extend permission. Successful edits retain the original feedback ID, booking/patient, creation time and deadline.
- `BEGIN IMMEDIATE` serializes changes; mismatched versions conflict. An exact retry of the just-saved version/content returns the existing result without changing Edited or creating another event, even if its response was lost near the deadline. Older retries cannot overwrite later edits. Unchanged content is a no-op within the window. Failed event writes roll back the edit.
- Patient identity/navigation are disabled during saves. Routine polling preserves the active editor's snapshot, so another session cannot silently replace its text; a stale save requires cancelling and reopening.

Verification:119 API tests passed, including five new tests for shared current values/report counts, preserved timestamps/deadline, exact clock boundary/offsets, retry after expiry, input/role/status restrictions, concurrency/stale edits, rollback and migration. Mobile TypeScript and dashboard production-build TypeScript passed; Android Hermes export and dashboard production build passed. One React Native accessibility type error was corrected before the final passing mobile check/export.

Browser verified new fictional feedback4/5 -> edit5/5/comment -> review/confirm -> Edited display -> reload persistence -> Noah separation. Staff count stayed3, displayed average changed4.3 to4.7 and updated content appeared. Old12October feedback shows editing closed. Only our existing synthetic follow-up `867db60f-0238-4b20-9801-b07ae652844d` (Ava/DrLim/L00129Oct9am) was completed and given new fictional feedback; no older feedback was modified. Evidence: `tmp/feedback-edit-fixture.json`, `tmp/feedback-edit-verified.png`.

User confirmed Android editing, review/confirm, reopening with Edited shown and patient separation on18October. The pending physical card is resolved; the 24-hour boundary remains verified by fixed-clock API tests. Runtime API session32551 PID97192 port8000 using `.venv-ai`; existing dashboard17348/3000 and Expo28048/8081 retained. AI/model/training, real auth, Word, dependencies and the user's `docs/ai/BASELINE_SETUP.md` edit are unchanged. No push, deploy or main merge.
