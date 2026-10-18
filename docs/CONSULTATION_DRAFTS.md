# Private consultation-note drafts

Implemented 18 October 2026. Separate from the existing assessment-review drafts.

Doctor flow: Consultation notes -> assigned called visit -> enter partial findings/follow-up -> Save draft. Reopening restores the saved text. Unsaved changes remain in the editor during routine polling, but only explicitly saved drafts survive leaving/reloading. Reload saved draft replaces unsaved edits. Publish consultation note previews both fields; Confirm consultation publication makes the confirmed text visible to the patient. Both fields remain required for publication, with findings limited to 2000 characters and follow-up to 1000.

Patient flow: My visits -> open own appointment -> Consultation note. No unfinished draft text is returned to patients. Published findings/follow-up appear through the existing views. Staff continues managing the queue without access to drafts. Other doctors cannot retrieve the assigned doctor's draft. These are demo identity boundaries; real authentication remains deferred.

Storage and safety:

- Additive `consultation_drafts` table keyed by booking, with doctor, findings, follow-up, version and saved timestamp. Existing published notes and visits are preserved.
- Doctor-only GET/POST `/visits/{booking_id}/consultation/draft`. Called/completed assignment is required to read; only called visits can save. Completed visits retain private, read-only saved drafts and cannot publish a new note.
- Saves serialize under `BEGIN IMMEDIATE`. Identical retries return the saved draft; changed content requires the current version. Stale content cannot overwrite newer text.
- Publication checks `draft_version` before inserting the immutable note/event and deleting the draft in one transaction. Failure preserves the draft. Exact published-content retries remain safe. Older callers without a version can publish only when no saved draft exists.
- Drafts are absent from consultation lists/detail, patient visit bundles, clinical history, care and notification responses. Only the dedicated doctor endpoint returns them.
- No autosave, late publication, published-note editing, draft deletion UI, new notifications, prescriptions or queue completion are included.

Verification: 110 API tests passed, including seven new draft tests covering persistence/privacy, limits/roles, conflicting and identical saves, stale publication, rollback, save/publication races, completed state and additive migration. Dashboard and mobile TypeScript checks and dashboard production build passed. Mobile UI is unchanged; no new Android export was needed.

Browser: a new fictional Ava visit L001, Dr Lim, 28 October at 9 am (`52f5882a-6863-4ab9-917d-d712d07d1960`) was created on an otherwise empty clinic date and called. Partial draft saved/reopened, explicit reload discarded an unsaved edit, polling retained edits, doctor switching cleared private content, patient detail hid unfinished text, publication preview/confirmation succeeded, Ava saw the final note and Noah did not. Existing visits were not modified. Fixture remains called, without prescription/bill/assessment sharing. Screenshot: `tmp/consultation-draft-published.png`; fixture: `tmp/consultation-draft-fixture.json`.

Optional Android check: Ava -> My visits -> L001 on 28 October at 9 am -> final fictional consultation note; close/reopen and confirm it remains; Noah should not see Ava's visit/note. This specific physical check has not yet been performed.

Runtime after verification: API session 72416, PID 52144, port 8000, using `.venv-ai`; existing dashboard PID 17348/port 3000 and Expo PID 28048/port 8081 retained. AI/model, Word report, real auth, dependencies and the user's `docs/ai/BASELINE_SETUP.md` edit are unchanged.
