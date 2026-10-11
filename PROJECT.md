# Smart Skin Disease System

Updated: 11 October 2026 (Asia/Kuala_Lumpur). Stage A: report review and discussion. No implementation approval yet.

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

## Architecture proposal - pending explicit approval

One repository: `apps/mobile` (React Native + Expo + TypeScript, ImagePicker), `apps/dashboard` (Next.js + TypeScript + Tailwind + shadcn/ui), `packages/shared` (types, validation and workflow rules). Share contracts and logic, not all UI components. Data access must be separate from screens.

Later hosted Supabase provides authentication, PostgreSQL and private file storage. Use versioned migrations and backend row-level permissions. Trusted server operations handle staff provisioning, privileged actions and transaction-sensitive workflows. A separate Python inference/training component is added only after selecting and evaluating an appropriate dataset/model. Training is reproducible and separate from the preview.

Reason to retain the user's provisional stack: one TypeScript language for both interfaces, camera/gallery support inside Expo Go, and fewer custom backend services. Flutter remains a valid alternative, but no demonstrated requirement currently warrants replacing the proposal. The report's Flutter/Node/Python/OpenCV claims must be revised if this proposal is approved. Exact dependency versions are not selected.

Tradeoffs: two UIs still need independent testing; hosted permissions require careful verification; custom on-device ML/OCR may require a development build; Python model serving introduces later hosting cost. Expo Go is a testing host, not an independently installable APK. EAS APK builds and store publication are separate later activities.

## Preview proposal - pending explicit approval

Demonstrate a patient opening a labelled demo, capturing/selecting a non-sensitive photo, previewing/confirming it, seeing a clearly simulated assessment, saving locally and reopening history. A doctor dashboard shows synthetic records and saves one review note/status locally. The two interfaces do not synchronise yet. Demo role selection is not authentication. No photos go to external services.

Working: navigation, permission/cancellation handling, basic file validation, durable local image/record saving and dashboard update persistence. Simulated: prediction, confidence, identities and records. Deferred from preview only: real backend, model, OCR, scheduling/queue, pharmacy, billing/payment integration, feedback/report workflows and real access control. All remain in final scope.

Preview completion: appropriate static/build checks pass; affected browser interactions verified; physical Android capture/gallery/cancel/deny/reopen tests confirmed by user; simulations clearly labelled. It is not a clinically validated diagnosis system.

Next real increment after preview: authorised patient submission reaches dashboard; authorised doctor review persists and appears on mobile. Subsequent increments connect registration/records, prescription-stock-billing transactions, feedback/reporting and remaining account/OCR features. Avoid building every frontend before backend integration.

## Costs and permission boundaries

Local mocked preview avoids paid hosting and account setup. Later Supabase/EAS/Vercel/model hosting quotas and limitations must be rechecked before committing to deployment; zero long-term cost is not promised. No services have been created or accessed.

Local inspection, planning documents and local checkpoints are authorised subject to the sandbox. Coding waits for explicit initial design/scope approval. Explain dependency downloads and install scripts before the first installation batch. Ask before external/private access beyond authorised scope, hosted changes, system installations, billing, publication, remote pushes, external photo/file transfer, destructive operations or broadening permissions. Never ask for secrets in chat.

## Decisions still needed

- Initial design/preview approval and whether lecturer expects more at the preview.
- Exact common-condition classes and legally usable, phone-photo-appropriate data.
- Final deadline and minimum acceptance evidence for each final module.
- Doctor access via explicit patient sharing versus assignment; staff prescription permissions; admin clinical access.
- Record correction/removal semantics, retention and photo consent.
- Appointment capacity, queue rules, payment provider/test mode, OCR approach and notification channel.

Official sources checked 11 October 2026: [Expo ImagePicker](https://docs.expo.dev/versions/latest/sdk/imagepicker/), [Expo FAQ](https://docs.expo.dev/faq/), [Next.js](https://nextjs.org/docs), [Supabase storage access](https://supabase.com/docs/guides/storage/security/access-control), [Supabase pricing](https://supabase.com/pricing). Context7 failed with an invalid API key; official web documentation was used as fallback.
