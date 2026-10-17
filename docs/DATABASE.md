# Data design

Status: proposed entity/schema design; role boundaries and shared core preview approved. No schema, migrations, hosted environment or implemented data access. Final scope retains all nine modules. Reference: report Figure 4.61, PDF 250; report permissions need alignment with approved rules below.

| Entity group | Relationships and purpose |
| --- | --- |
| Auth users, profiles, controlled role assignments | Provider identity links to profile; privileged roles provisioned by trusted operations |
| Doctor profiles, specialities, schedules, availability blocks | Doctor has specialities and available capacity; registration references patient and doctor/slot |
| Registrations and queue entries | Patient visit -> optional queue; explicit states, timestamps and concurrency rules |
| Assessment sessions, private images, prediction results | Patient owns session; image metadata points to private storage; one session has ranked outputs and model version |
| Conditions, educational advice and doctor matching | Versioned label/advice mapping; prediction confidence separate from medical risk |
| Doctor reviews, medical entries, versions, attachments and sharing grants | Patient records link to visit/assessment as applicable; doctor authors review/entry; explicit access grants and audit events |
| Medicines, stock batches/movements, prescriptions and items | Prescription links patient/doctor/visit; dispensing records batch/quantity and stock transaction |
| Services, invoices, invoice lines, payment records | Visit/prescription produces priced lines; payment references invoice, status and external reference if applicable |
| Feedback and rating items | Patient's eligible completed visit; edit window and visibility rules |
| Report definitions/export history and audit events | Restricted derived reports with filters; trace actor and sensitive state changes |

This is a whole-system entity map, not a commitment to one table per item. Avoid speculative fields. Inventory's single current batch/expiry in the report needs review for multi-batch dispensing. Record sharing is not represented adequately by merely a user role.

## Approved ownership and access boundaries

Patients read/update allowed parts of their own profile and see their own records. They cannot assign privileged roles. Doctors see explicitly shared records or records authorised by patient booking; authored clinical notes are separate from AI results. Staff receive minimum queue/billing/pharmacy data needed, not blanket clinical access. Admin user operations and permitted reports do not imply unrestricted clinical browsing. Grant lifetime/revocation and report field details remain to specify.

Private storage must enforce owner/grant access through backend policies. No public image URLs or privileged client credentials. Use migrations for schema/policies; verify cross-user denial, not only successful requests. Stock dispensing/payment updates require atomic/idempotent trusted operations; exact rules await detailed module audit.

Proposed preview contracts: assessment session with synthetic patient, timestamps, image reference/status and prediction origin=`simulation`; separate doctor review; doctor slot/booking with capacity/state; queue entry with status/order; prescription/items with dispensing state; invoice/lines and payment mode=`simulation`. Both UIs must retrieve the same saved records through one shared backend. Mobile local image paths must be durable, not temporary picker URIs; local paths cannot serve as cross-device image URLs. Image transfer/storage needs authorised environment. None implemented.

Migration status: none. Environment: none authorised. Data retention, sharing revocation, detailed grants and record removal are unresolved. Prefer versioned corrections/soft removal over report's permanent deletion, subject to agreement.

## Implemented local demo, 11 October 2026

Earlier entity map remains the final design plan. Local demo schema now exists in apps/api/app/store.py: slots (doctor/date/time/capacity), bookings (patient/slot/token/status/request key), events (actor/action/time). SQLite data under ignored apps/api/data/demo.sqlite3; no hosted migrations/environment. Request keys unique per patient; BEGIN IMMEDIATE serialises capacity/queue transitions. Cancelled rows release capacity but preserve tokens/history; completed rows remain used capacity. Queue tokens increase per doctor/day; order is appointment time then token. Availability seeded for the next two days at startup, two places per slot. Demo header scopes requests but is freely forgeable, not authentication. No clinical notes/photos stored or transferred.

## Implemented prescription/billing demo

Additional SQLite tables: medicines (placeholder name, integer cents, nonnegative stock), prescriptions (one per booking, assigned doctor, issued/dispensed), prescription_items (unique medicine per prescription, positive quantity, directions), invoices (one per completed booking, integer total, unpaid/paid, simulation mode/time), invoice_lines (frozen description/quantity/unit cents). Existing records preserved via CREATE TABLE IF NOT EXISTS and INSERT OR IGNORE catalog seed. No hosted migration.

All mutations use BEGIN IMMEDIATE transactions. Dispensing deducts each stock atomically and rolls back all deductions if any item is short. Repeats return saved results. One immutable prescription and invoice per visit; new prescription blocked after billing. Invoice values calculated on server, snapshotted as integer cents. Payment requires dispensed prescription when present and records simulation only, once, with audit event. /care filters patients to own visits and doctors to assigned visits; staff gets operational details. Headers remain spoofable demo identities, not authentication. No clinical notes/photos added.

Skin assessment storage: assessments(id,patient_id,request_id unique per patient,source_hash,photo JPEG BLOB,width,height,created_at). Photo/metadata inserted atomically, repeats return same row; same request/different bytes rejected. Listing returns latest100 own metadata, detail returns own photo data URI; staff/doctors denied pending explicit sharing. Simulation fields currently fixed response template, no model analysis; before adding real inference, persist prediction/model version per assessment so old results remain stable. No public image URLs/external storage. Filename/source metadata not stored; normalized JPEG strips EXIF/GPS. Database itself stores photos and must remain synthetic/non-sensitive until real identity/storage security is implemented.
Doctor review increment: assessment_shares references assessments, records patient/doctor/message/request/created/revoked timestamps. Partial unique index permits only one active share per assessment/doctor; historical revoked grants remain. Per-patient request keys are stable retries and cannot silently reactivate revoked grants. assessment_reviews references a unique share and saves doctor/note/follow_up/created time. Published content fixed; patient retains it after revocation, doctor loses API access. BEGIN IMMEDIATE serializes mutations. No changes to existing photo/booking/care records. Demo headers remain impersonable; replace with verified accounts and equivalent database access policy before real data.
Appointment linking: additive nullable booking_id FK on assessment_shares. Existing direct grants/reviews preserved. active_direct_share enforces one active assessment/doctor grant with no visit; active_visit_share enforces one active grant per booking. Direct and visit grants remain independently revocable. Cancellation transaction sets revoked_at on that booking's active grant only. New links require own assessment and own eligible waiting/called visit; doctor derived from booking. Completed visits retain historical consent, cancelled visits rejected by doctor reads. Old request retries cannot silently reactivate revoked/cancelled links. New consent after revoke creates a new grant.
Consultation notes increment: consultation_notes(id, unique booking_id FK, doctor_id, findings, follow_up, created_at). Publication uses BEGIN IMMEDIATE and writes one consultation-published event with no note text in operational events. Assigned called visit only for initial publication; existing exact content retry safe, replacement conflicts. Published notes retained on completion or linked-assessment revoke; note access follows own patient/assigned doctor visit authorization. Staff API rejects consultation access, /care excludes notes. List omits photo bytes; doctor detail fetches only active appointment grant. No schema/data changes to existing clinical-review, billing or photo records.

## Counter booking

POST /counter-bookings accepts patient_id, slot_id and request_id from staff-demo. It uses the existing bookings table and Store.book transaction, without migration. Shared patient/request keys prevent cross-channel duplicate retry; the existing active patient/slot and capacity rules apply to counter and phone bookings alike. New counter bookings log events.action=counter-booked and actor_id=staff-demo once; retries do not add events. The patient remains the booking owner. Demo headers remain spoofable and must be replaced before real data use.

## Rescheduling

New reschedules table: primary key(actor_id,request_id), old_booking_id/new_booking_id foreign keys, target slot_id, created_at. POST /bookings/{id}/reschedule uses BEGIN IMMEDIATE to check ownership/future-waiting state/target availability and duplicates, cancel old, create new queue token, update or revoke active appointment grants, insert mapping and paired rescheduled-from/to events atomically. No existing data removed. Booking responses derive nullable rescheduled_to_id for history display. Same-doctor grants move their booking_id; changed-doctor grants retain original booking_id and receive revoked_at. Direct grants untouched. Actor/request mapping persists retries independently of the new booking's later state.

## Visit feedback

visit_feedback: id, unique booking_id(FK), patient_id, integer rating CHECK1..5, comment, created_at. POST /visits/{id}/feedback requires own patient identity, completed booking, strict integer1-5 and comment<=1000. Transaction creates one immutable record and feedback-submitted event; exact content retry returns saved record; changed retry conflicts. GET /feedback allows own patient records or staff-demo latest100; doctors denied. Payload includes operational Booking metadata, never consultation text or assessment photos. Staff aggregate average is computed from displayed submissions only. Real account identity enforcement remains future work.

## Stock receiving

stock_receipts: id, medicine_id FK, positive quantity, reason, stock_before, stock_after, actor_id, unique request_id, created_at. POST /stock/receive staff-only strict integerquantity1-1000, nonblankreason<=300, request8-100. BEGIN IMMEDIATE adds to latest stock (cap100000) and inserts receipt atomically; identical retry returns saved receipt, mismatched content conflicts. Existing dispense transaction uses same medicines.stock and prevents negative balance/duplicate deduction. GET /stock staff-only returns medicines, latest100 named receipts and low_stock_threshold5. Receipts retain fixed snapshots independent of subsequent dispensing. No dispensing-ledger migration/new medicine/expiry tracking.

## Patient visit details

GET /bookings/{booking_id}/details patient-only, own booking enforced before child record queries; others404, staff/doctors403. One BEGIN read transaction bundles operational Booking, linked assessment_shares/reviews+simulation metadata(noBLOB), consultation note, prescription/items, invoice/lines, feedback and optional replacement Booking. Latest100 linked grants pervisit; direct shares excluded. Uses existing tables without migration. Revoked appointment review history retained; same-doctor rescheduling moves active grant, old visit links replacement; changed-doctor oldgrant revoked, newvisit not auto-shared.

## Daily report

No new tables. Staff-only GET /reports/daily validated clinic_date returns single-read-transaction aggregates. Booking count grouped by current status except EXISTS(reschedules.old_booking_id) => rescheduled. Billing SUM invoices joined to appointment slots; paid+unpaid=billed. Stock independently aggregates receipt quantity by date(created_at,'+8 hours') and dispensed prescription-item quantity by date(dispensed_at,'+8 hours'), preventing invoice-line join duplication. Feedback COUNT/AVG by Malaysia submission date. Empty totals0/average null. Aggregate operational output only; no patient names, clinical text/photo or comment values. generated_at UTC snapshot timestamp, displayed Malaysia time. No frozen historical status model/cashflow ledger implied.


## Patient background addition
patient_backgrounds(patient_id PRIMARY KEY, allergies TEXT, medicines TEXT, conditions TEXT, version INTEGER, updated_at TEXT UTC). Created additively at Store startup; no existing records changed. Empty/no row returns blank fields, version0, null timestamp. Own-patient read/write; BEGIN IMMEDIATE compare revision + upsert, stable same-value retries. Doctor access derived from assigned called/completed consultation, no staff access. This is latest patient-provided info, not a version history or immutable visit snapshot; it does not modify consultation notes.

## Medicine catalogue and issued snapshots
Additive medicines columns strength/form (TEXT NOT NULL DEFAULT empty), request_id nullable with unique filtered index. POST creation stock0; duplicate name/strength/form checked case-insensitively in serialized transaction, identical request retry returns current item without adding stock. Public operational catalogue omits request key.
prescription_items now has saved name, price_cents, strength, form. Legacy rows backfilled at first startup from current catalogue where name NULL; cannot reconstruct earlier unsaved catalogue history. Existing invoices remain unchanged. New prescriptions snapshot item identity/price at issue; dispensing still updates live stock, billing uses snapshot. Subsequent startup never refreshes saved snapshots. Catalogue edit/archive and supplier/batch expiry remain separate scope.

## Appointment slot management
slots.closed INTEGER NOT NULL DEFAULT0; request_id nullable TEXT with unique filtered index. Existing rows remain open; seed inserts explicit original columns and INSERTORIGNORE preserves closure. Staff creation compares doctor/start timestamp in normalized Malaysia +08:00, stores fixed clinic_date/capacity, starts future only. Closure retains row and prohibits any booking history; BEGINIMMEDIATE shares serialization with book/reschedule. Public slots filter closed=0 and omit keys. Staff future view includes closed rows and all-history counts plus active availability. No deletion or changing booked slot identity/time/capacity.

## Patient notifications
patient_notifications(id PRIMARY KEY, patient_id, kind, source_id, target_id, title, message, created_at UTC, read_at nullable UTC), UNIQUE(patient_id,kind,source_id). Queue source_id/target_id=booking; review source_id=share,target_id=assessment. Created only for new queue calls and initial review publication inside source transaction. Generic messages omit clinical content/photos. Patient-only latest100 ordereddescending plus totalunread snapshot, serialized own-ID mark-read preserves first timestamp. No retroactive backfill or push delivery.

## Doctor profiles
New doctor_profiles(doctor_id TEXT PRIMARY KEY, specialty TEXT NOT NULL, expertise TEXT NOT NULL JSON array, version INTEGER NOT NULL, updated_at nullable UTC). Existing demo doctors insert once with Not specified/empty/version0; subsequent startup preserves saved edits. Read endpoint /doctors requires a recognised demo actor; POST /staff/doctors/{id} staff-only. Specialty trimmed/nonblank/max80, distinct expertise keys general/acne/eczema/psoriasis; empty allowed. Serialized optimistic version check protects changed writes; identical content retry returns current record. Public display data only; this adds no clinical access. Names/IDs remain fixed demo identities. Matching and recommendation rules are not yet implemented.

## Doctor matching query
No schema change. GET /doctor-matches patient-only; exactly one supported concern or owned assessment_id. Metadata lookup/profile read in one read transaction; category map has general fallback, output includes concern/source/assessment reference/message and all doctor profiles with match_level/reason sorted concern/general/none. No assessment/photo sharing, clinical content or recommendation state stored. Mobile joins current slots to doctors by doctor_id; normal booking endpoint remains authoritative for availability. Simulation origin retained and clearly disclosed.
