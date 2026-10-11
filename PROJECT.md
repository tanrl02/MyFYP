# Smart Skin Disease System

Updated: 11 October 2026 (Asia/Kuala_Lumpur). Initial architecture, core preview scope and access rules approved. Detailed report audit and implementation remain to do.

## Authorised locations and source

- Project: `C:\Users\chenr\SmartSkinDiseaseSystem\MyFYP`.
- Current editable report: `C:\Users\chenr\SmartSkinDiseaseSystem\BACS3403_FinalDoc_TanRiLi.docx`, newly supplied by user. Treat this as the current report for all future edits/reviews; do not assume it matches the earlier PDF.
- Earlier reference: `C:\Users\chenr\SmartSkinDiseaseSystem\BACS3403_FinalDoc_TanRiLi.docx.pdf` (302 PDF pages), preserved unchanged.
- User authorises updating the editable report when approved design/project changes would make it inconsistent. Before the first edit save an untouched backup; preserve existing formatting and document report changes/verification. Do not describe pending proposals as approved or completed functionality.
- User's starting instructions were provided as an attachment. Their operative requirements are recorded here and in the companion documents; do not rely on access to that attachment in a new chat.
- Workspace-write sandbox is declared; network access is restricted and `.git` is a read-only protected path in the supplied permission profile. Branches do not provide security isolation.

## Confirmed user requirements

- Final project must retain the report's substantial scope: all nine modules remain in scope. A smaller preview must not be treated as an approved reduction of the final project.
- Review the whole system, not just the AI screens.
- Existing trained models may be used, but meaningful fine-tuning and evaluation work is required.
- Target common skin conditions; no dataset or model exists yet. Exact classes remain undecided.
- Very low budget, Android phone, minimal manual setup, TortoiseGit for visual Git use.
- Tentative preview: 22 October 2026. Final deadline unknown. Lecturer revisions expected.
- Save continuity in this repository. Never invent implementation, measurements, citations, or phone test results.
- Agent owns detailed report review and asks concise decision questions; user is not expected to audit documents line by line.

## Final scope inventory

1. Account management: patient signup, login/logout, verification and recovery; OCR IC extraction.
2. User management: own profile; admin create/search/filter/update/deactivate users.
3. Registration: online and counter visits, availability, cancellation, editing and queues.
4. AI skin assessment: image submission, real inference, history, educational advice and doctor matching.
5. Medical records: consultations, attachments, sharing, change history and corrections/deletion semantics.
6. Pharmacy: prescriptions, verification/dispensing, medicines, restocking, expiry and threshold alerts.
7. Billing: invoices, counter payment records, online payments and receipts/history.
8. Feedback and ratings: completed-visit feedback, viewing/editing/deleting and time limits.
9. Reports: role-restricted operational reports, filters and exports.

Details and unresolved contradictions: `docs/REPORT_REVIEW.md`. Inventory inclusion is not approval of every original technical claim.

## Approved architecture

User approved one shared Python API for mobile and dashboard, containing system logic and AI inference; Supabase supplies managed authentication/database/private storage. No separate Node.js business API. User prefers selection cards; keep turn active while collecting answers because cards disappear after final responses. Database permissions/migrations still require maintenance; a single custom backend does not eliminate managed services or deployment requirements.

One repository: `apps/mobile` (React Native + Expo + TypeScript, ImagePicker), `apps/dashboard` (Next.js + TypeScript + Tailwind + shadcn/ui), `packages/shared` (types, validation and workflow rules). Share contracts and logic, not all UI components. Data access must be separate from screens.

Later hosted Supabase provides authentication, PostgreSQL and private file storage. Use versioned migrations and backend row-level permissions. The shared Python API handles staff provisioning, privileged actions, transaction-sensitive workflows and inference. Model training scripts are a separate offline workflow in the same repository, not a second application backend. Training is reproducible and separate from the preview.

Reason to retain the user's provisional stack: one TypeScript language for both interfaces, camera/gallery support inside Expo Go, and fewer custom backend services. Flutter remains a valid alternative, but no demonstrated requirement currently warrants replacing the proposal. The report's Flutter/Node/Python/OpenCV claims must be revised if this proposal is approved. Exact dependency versions are not selected.

Tradeoffs: two UIs still need independent testing; hosted permissions require careful verification; custom on-device ML/OCR may require a development build; Python model serving introduces later hosting cost. Expo Go is a testing host, not an independently installable APK. EAS APK builds and store publication are separate later activities.

## Approved core preview

User rejected the minimal photo-only preview and required the following core workflows. User approved shared saved records between phone and dashboard; AI predictions and payment processing remain simulated.

1. Patient skin assessment: capture/gallery, preview/confirmation, labelled simulated result and history.
2. Appointment booking: sample doctor availability, booking and cancellation.
3. Patient queue: queue number and staff call/status updates.
4. Prescriptions: doctor creates prescription; authorised staff view and record dispensing.
5. Billing: generate visit/prescription bill and record clearly simulated payment.

These form one connected demonstration using synthetic patients, staff, medicines and prices. Saved bookings appear on the dashboard; queue/prescription/billing updates appear on mobile. Separate unsynchronised sample stores are no longer the approved target. Keep source of result (`simulation` versus model) separate from doctor findings and payment mode separate from real transactions. No clinical reliability or actual payment processing claims.

Working target: navigation, permission/cancellation handling, basic file validation, durable saving, shared record retrieval/updates and five core workflow state transitions. Simulated: AI output, financial transactions, identities and clinical/sample data until real auth is connected. Deferred from preview only: trained inference, OCR, real payment gateway, complete inventory operations, feedback/reporting and remaining final-module details. All nine modules remain in final scope. Do not claim demo role selection verifies backend access control; real identity/access rules require implementation and separate tests.

Preview completion: appropriate static/build checks pass; affected browser interactions verified; physical Android capture/gallery/cancel/deny/reopen tests confirmed by user; simulations clearly labelled. It is not a clinically validated diagnosis system.

Implementation starts with one shared booking/queue workflow, then extends the same saved data into records, prescriptions and billing; skin-photo/result workflow can be added with simulated inference independent of model research. Replace mocks gradually and connect real auth/private storage. Avoid building every frontend before backend integration.

## Costs and permission boundaries

Use local synthetic data during development. Shared records require a running common API/data store; hosting, development environment and account setup are still to be resolved. Supabase/EAS/Vercel/model hosting quotas and limitations must be rechecked before committing to deployment; zero long-term cost is not promised. No services have been created or accessed.

Local inspection, planning documents, approved core implementation and local checkpoints are authorised subject to the sandbox. Initial design/scope/access approval was received; do not request it again. Explain dependency downloads and install scripts before the first installation batch. Hosted environment and data transfers are not authorised by design approval. Ask before external/private access beyond authorised scope, hosted changes, system installations, billing, publication, remote pushes, external photo/file transfer, destructive operations or broadening permissions. Never ask for secrets in chat.

## Approved clinical access

Patients see their own records. Doctors access records through explicit sharing or patient-authorised booked visits. Staff see only necessary registration/queue, prescription and billing fields. Admins manage accounts and permitted reports without automatic access to all clinical notes/photos. Enforce permissions in the backend; unauthorised role/self-promotion and cross-patient access must be denied. Detailed grant lifetime/revocation still needs specification.

## Decisions still needed

- Hosted development environment and permitted external data transfers; preview deployment details.
- Exact common-condition classes and legally usable, phone-photo-appropriate data.
- Final deadline and minimum acceptance evidence for each final module.
- Detailed consent grant lifetime/revocation and report field visibility within approved role boundaries.
- Record correction/removal semantics, retention and photo consent.
- Appointment capacity, queue rules, payment provider/test mode, OCR approach and notification channel.

Official sources checked 11 October 2026: [Expo ImagePicker](https://docs.expo.dev/versions/latest/sdk/imagepicker/), [Expo FAQ](https://docs.expo.dev/faq/), [Next.js](https://nextjs.org/docs), [Supabase storage access](https://supabase.com/docs/guides/storage/security/access-control), [Supabase pricing](https://supabase.com/pricing). Context7 failed with an invalid API key; official web documentation was used as fallback.


## Update 11 October 2026 report work deferred

User update: report editing is deferred until implementation is complete to save tokens/usage. Do not continue Word editing/rendering now. Preserve the original report for a later comparison with actual implementation. Prepared candidate is not applied.

## Implementation update, 11 October 2026

Booking/queue code now exists, starting from 87ad49d. Synthetic SQLite is the local shared demo store; planned Supabase auth/PostgreSQL/private storage has not been connected. Demo identities are not secure authentication. Dependency versions are recorded in package manifests/lockfile and Python requirements. Remaining preview flows and all final modules still required. Original Word stays unchanged per latest user instruction.
