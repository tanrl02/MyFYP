# Handoff

Updated 11 October 2026 (Asia/Kuala_Lumpur). Initial architecture/core preview/access approved. Agent owns report review; user need not review line by line. Use one selection card at a time and keep turn active while awaiting answers because cards disappear after final replies.

## Confirmed decisions

- Final scope retains all nine report modules.
- Expo/React Native patient UI and Next.js Doctor/Staff/Admin dashboard; one shared Python backend for system logic and AI. Supabase managed auth/database/private storage remains planned; no separate Node.js business backend.
- Preview: skin assessment/photo/history, appointment booking, patient queue, prescriptions and billing, with shared saved records across both UIs. AI predictions and payment processing simulated.
- Patients see own records; doctors receive explicitly shared or booking-authorised access; Staff see only necessary queue/prescription/billing fields; Admins have account/permitted-report access without automatic clinical access.
- Common conditions; no dataset/model. Pretrained weights plus meaningful fine-tuning/evaluation required. Exact classes remain open.

## Actual state and checkpoints

- Project/source report locations in PROJECT.md. Current editable DOCX supplied; unchanged. User authorises report alignment; save untouched backup before first edit and visually verify.
- Branch main. Baseline a889116; report requirement 965a92a; backend preference f815d11. Current decisions checkpoint titled `docs: approve shared core preview and access boundaries`; resolve exact hash through Show Log.
- No application checkpoint; no app/backend code, dependencies, model, database or migration exists.
- Uncommitted changes at this decisions checkpoint: none expected; verify status on resume. Temporary text/rendered pages under ignored tmp/.
- Supabase: no selected/authorised environment; no service access or hosted mutation. No external photo/private-file transfers.
- Agent checks: source inspection, initial review within recorded coverage, public source checks, Markdown/diff checks. No Android/browser/application/access tests passed.

## Remaining review and technical limits

- Detailed report coverage/unreviewed sections in REPORT_REVIEW. Do not claim full audit or assume DOCX matches historical PDF pagination.
- Context7 API key invalid; official web docs fallback. pypdf/pypdfium2 available; PyMuPDF unavailable.
- DOCX renderer preflight failed: missing LibreOffice soffice.exe; temporary-directory cleanup also failed. Loader did not supply LibreOffice path. Historical PDF cannot verify changed DOCX layout. No Word edits made.
- Initial implementation approval granted; do not repeat design approval. First dependency batch explanation, actual sandbox and separate hosted/private-transfer permissions still apply.

## Exact next task

Audit booking/queue/prescription/billing detailed requirements in current DOCX, reconcile state transitions/transactions, then prepare first shared booking/queue increment and versioned contracts. Define working/mock boundaries and tests; explain first dependency batch. Identify/authorise environment before hosted changes. No paid resources, remote publication/pushes or external photo transfers approved.

Completion: patient booking appears in authorised staff queue; queue update persists and is retrieved on mobile; cancellation/capacity/duplicate-action cases handled; synthetic data; agent checks recorded, Android checks pending user confirmation. Extend prescriptions/billing with same saved records afterwards.

Maintain report alignment plan while resolving verified DOCX editing/rendering. Preserve final nine-module scope and distinguish planned/achieved functionality. Continue dataset/model licence, modality and fine-tuning feasibility independently. No accuracy claims until measured.


## Update 11 October 2026 report work deferred

Latest user instruction supersedes report-alignment work: STOP editing/rendering Word until implementation completes to save tokens/usage. Original DOCX remains unchanged (verified SHA256 matches supplied version). Backup in parent report-backups; unverified candidate/QA under ignored tmp/docx. Helper scripts are unfinished report-work checkpoints, not application code. Current branch docs/report-alignment; return to main after saving checkpoint. Next task remains shared booking/queue implementation; do not reopen report QA.
