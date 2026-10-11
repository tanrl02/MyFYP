# Report review

Updated 11 October 2026. Initial substantive review, not a completed line-by-line audit. Original report preserved at the location in PROJECT.md. Locators below use PDF page numbers; the report's printed chapter page is generally PDF page minus 7. Front matter differs.

## Current editable source and synchronisation

User has now supplied `C:\Users\chenr\SmartSkinDiseaseSystem\BACS3403_FinalDoc_TanRiLi.docx` as the current editable report. Read-only OOXML inspection found 5,034 body/table paragraphs, 82 tables and 180 media files; no tracked insertions/deletions. SHA256 of supplied version: `d5920f36d0e730dc8368c4cceff9a9ed94bc8990e30d7b2759d85a71014168bd`.

Confirmed in this DOCX: abstract still claims completed outcomes and Flutter implementation; algorithm still maps confidence to medical risk; no Supabase text found. Other differences from PDF have not yet been exhaustively compared. Existing PDF page references are historical locators, not verified DOCX pagination.

User requires report updates alongside approved design/implementation changes. Save untouched DOCX backup before first edit, preserve report layout, update affected prose/tables/diagrams/references where necessary, render and visually verify edited report, and log actual changes here. No DOCX edits performed yet because initial design is still pending. Agent performs review; user answers decision questions rather than reviewing each paragraph.

## Coverage and limitations

- Read abstract, contents, Chapter 1 objectives/scope/schedule (PDF 4, 6-20), technical feasibility (39-42), interview text (44-48), summary functional/nonfunctional requirements (182-186), AI use cases (134-142), selected account/medical use cases (67-71, 143-150), AI UI descriptions (237-244), security design (254-257) and algorithm text (278-279).
- Visually inspected scope, overall actors, AI result UI, ERD, class/deployment overview (17, 66, 239, 250, 251, 278); ERD inspected at larger resolution. Fine-grained class/deployment labels still need a closer pass.
- Skimmed literature, survey results, references and appendices. Full text extracted locally but extraction is not proof every page was reviewed.
- Still pending: detailed user-management, reports, feedback, billing, pharmacy and registration use-case tables; all activity/sequence diagrams; remaining UI pages; complete bibliography/citation audit; appendix image/form inspection and raw survey evidence. Review these before corresponding implementation decisions, without narrowing the final scope.

## Report's explicit objectives and workflows

Section 1.1 (PDF 9-10) combines skin self-assessment, longitudinal patient records, hospital operations and doctor-patient communication. Section 1.5.2 (17-19) and 3.2.1 (182-184) define nine modules. Actors are Patient, Doctor, Staff and Admin; User is the generic actor (Figure 3.20, PDF 66).

Patient: account/profile -> upload photo -> AI results/history -> advice/doctor recommendation -> register a visit -> consultation/medical record -> prescription/bill/payment -> feedback. Staff: counter registration/queue and pharmacy/billing operations. Doctor: schedules/queue, authorised records and prescriptions. Admin: users, doctor availability and reporting. This connected sequence is our interpretation across the module descriptions, not a single mandatory ordering stated in the report.

Prediction requirements explicitly include condition labels, confidence, risk, history, educational care suggestions and doctor recommendations. Image formats: JPEG/PNG, minimum 224x224 (4.7, PDF 278); upload limit described as 5 MB (4.4, 257). Format validation is feasible; automatically judging skin clarity/body region requires additional logic and evidence.

## Findings and proposed revisions

| Finding | Evidence | Recommendation / status |
| --- | --- | --- |
| Completed system/results claimed without implementation | Abstract, PDF 4; security prose, 255-257 | Rewrite as proposed work until code and evaluation exist. User confirms no implementation; empty repository observed. |
| Scope substantially exceeds a small preview | Nine modules, 17-19 and 182-184 | Retain all nine for final project, per user. Deliver connected increments; preview scope requires approval. |
| Old/invalid timeline | 1.4.2, 14-16: 31 June 2025 and documentation in December 2024 | Replace with actual milestones; tentative preview 22 October 2026, final deadline unknown. |
| Naming/template drift | Cover says Smart Skin Health System; use-case figure says Smart Skin Disease System; headers say Project Title/BACS3413 | Confirm official title/course details before eventual report editing. |
| Login contradicts its own postcondition | Login basic flow, PDF 68 redirects successful user to login; PDF 69 says dashboard. A2/A3 labels swapped | Redirect to authorised role home and align alternate-flow references. |
| Model confidence used as medical risk | 4.7, PDF 279 maps >85% to High Risk | Remove this mapping. Confidence concerns prediction uncertainty; it does not measure clinical severity. Keep uncertainty separate; any future risk rules need explicit justification. |
| Condition/model/dataset mismatch | 4.7, 279 names acne/eczema/psoriasis and HAM10000/DermNet | Exact labels not fixed. Dataset choice must support common-condition phone photos; see research below. |
| Preprocessing prescribed without validation | 4.7, 279 prescribes blur, CLAHE, optional grayscale | Match selected model's training inputs; assess transformations experimentally rather than assume they improve performance. |
| Numeric guarantees lack evidence | 3.2.2, 184-186: 5-second inference, 20 requests/min, 99.9% uptime and 98% successful requests | Treat as proposed targets with hardware/network/load definitions and measurement plans; no pass claims. |
| Conflicting clinical access | 4.4, 256 says staff cannot see private medical content; edit/attachment cases, 146/149 allow authorised staff | Specify operation-by-operation permissions. Separate pharmacy prescription fields from general clinical records. |
| Broad admin privilege and sharing unclear | 4.4, 256; record sharing requirements, 184 | Decide admin clinical access and patient consent/doctor assignment; enforce rules in backend. |
| Permanent deletion conflicts with accountability/history | Delete case, 148-149 vs medical log requirements, 184 | Propose versioned corrections/soft removal with reasons. This is pending approval, not a silent requirement change. |
| ERD insufficient for consent and transaction integrity | Figure 4.61, 250 | Existing diagnosis session/result separation is useful. Add explicit sharing/attachments/audit ownership; review capacity, batch inventory, invoice lines and atomic operations before schema approval. |
| Security design not implementation evidence | 4.4, 255-257 claims AES-256 fields, lockout and ORM use | Document actual provider controls, key management and tests. Do not claim compliance from encryption prose. Stack mentions SQLAlchemy/Django ORM despite Node proposal. |
| Survey arithmetic/denominators inconsistent | 3.1.2, 65: 79 displayed as 79%, text 77.5%; 71 as 71%, text 69.6%; 61: 42/102 shown as 42.2% | Recalculate from original anonymous responses. PDF 53 says respondents with skin problems but counts exceed the 64 positive respondents on 52; clarify eligibility and denominator. |
| Interview description says 12 questions but numbered presentation ends at 10 | 44 and 46-48 | Confirm original evidence; preserve real findings and correct narration. Never manufacture answers. |
| UI shows values without measured analysis | AI result UI, 239-240 | Sample confidence, region and quality labels are mockups, not verified model outputs. Label simulations in prototype. |

## Retain, revise, investigate

Retain: nine-module functional inventory, incremental delivery, patient history, doctor review, private photos, role separation, audit history, clear AI disclaimers and permission/cancellation flows.

Revise: unsupported completed-work/outcome claims, timeline, inconsistent flow references, confidence-to-risk conversion, architecture after approval, schema/access details and evaluation promises. Preserve the source report; no report edits performed.

Investigate: original survey/interview evidence, every reference supporting a technical/medical claim, dataset/model licences, condition coverage, consent and access, OCR/payment/notifications and final acceptance criteria. A cited paper's existence does not establish the report's interpretation is correct.

## Early prediction research - no selected model or downloaded data

User requires common skin conditions with meaningful fine-tuning work. [HAM10000 original paper](https://pubmed.ncbi.nlm.nih.gov/30106392/) describes dermatoscopic pigmented lesions; it does not establish support for acne/eczema/psoriasis smartphone photos. Such a model cannot be adopted just because it is labelled skin disease detection.

[DermNet image licence](https://dermnetnz.org/image-licence) prohibits using freely available website images for AI training/testing; a separately licensed dataset is offered for a fee. No scraping or download is authorised or performed.

MobileNetV2/EfficientNetB0 are candidate backbone architectures, not ready dermatology classifiers. No suitable existing disease model, its licence or hosting route has yet been verified. Next research must compare legally usable clinical-photo datasets and compatible pretrained weights for a small fixed label set, including class balance, image modality, annotation quality and skin-tone coverage.

For training: record source/licence, exact labels, preprocessing and model version; split by patient/lesion when identifiers exist to avoid leakage; save seeds/configuration; compare baseline with fine-tuned model; report per-class precision/recall, macro-F1, confusion matrix and held-out limitations. Calibration/uncertainty and unsupported-image handling need evaluation. Accuracy and phone-photo suitability remain unmeasured. Select hosting after measuring model size, latency and budget.

## Discussion decisions

11 October 2026: user rejects narrowing final scope and requires review of the full project. All nine modules stay in final scope. Existing pretrained models plus fine-tuning are allowed/required to demonstrate effort. Common skin conditions intended; no dataset/model supplied. Exact prediction classes, initial architecture and preview implementation remain pending approval.

Later decisions supersede initial pending notes: approved shared Python backend, mobile/web interfaces with managed Supabase services, five core preview workflows (skin assessment, booking, queue, prescriptions, billing), shared saved records, simulated AI/payment processing, and scoped patient/doctor/staff/admin clinical access. No coding/training/hosted work has occurred.

Required report alignment batch: abstract/methodology and feasibility stack; incremental milestones; mobile framework rationale; deployment architecture; AI simulation versus future fine-tuning; shared workflow/persistence descriptions; security access rules including admin and staff; test criteria distinguishing target from achieved evidence. Do not delete final modules or claim prototype functionality before implementation.

DOCX rendering preflight failed on 11 October 2026: packaged renderer could not find LibreOffice `soffice.exe`; cleanup also encountered temporary-folder permissions. No edited DOCX has been produced. Preserve source until a verified editing/rendering path exists. Rendering the historical PDF cannot verify changed DOCX layout.


## Update 11 October 2026 report work deferred

Report editing paused by user until implementation completes. A 16-paragraph candidate and unchanged backup were prepared; original DOCX remains byte-identical to supplied version. Word exported baseline/candidate (305 pages); PNG generation succeeded but renderer cleanup failed under sandbox. Outside-sandbox retry was declined. Visual QA incomplete; candidate is not applied or delivered. Stop further report QA/edits now.

## Booking/queue implementation decisions, 11 October 2026

Implemented demo rules: two sample doctors, next two days seeded, two places per slot; no past bookings; one active booking per patient/slot; cancellation only future waiting visits; capacity restored, history/token retained; call one patient per doctor/date, appointment-time order then token; only called visits complete. These are explicit demo assumptions pending full final-scope scheduling rules. Future dates can be rehearsed by staff. No counter registration/edit/reschedule/check-in or production consent/auth yet. Do not treat this increment as a full report audit. Word editing is deferred by user.
