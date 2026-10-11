# Feedback

| Date | Source / item | Decision and affected work | Implementation / verification |
| --- | --- | --- | --- |
| 11 Oct 2026 | User: report is source; MyFYP is project to change | Preserve original report, write project changes inside MyFYP | Planning documents created; code approval pending |
| 11 Oct 2026 | User: do not narrow review/final scope; too small may fail | Retain all nine report modules. Small preview can only be a milestone | Reflected in scope/review/tasks; no implementation |
| 11 Oct 2026 | User: pretrained model plus fine-tuning acceptable; effort required | Plan reproducible fine-tuning and comparative evaluation | Data/model selection pending; no training performed |
| 11 Oct 2026 | User: common conditions; no dataset/model yet | Research clinical-phone-photo data; exact classes pending | Initial licence/modality issues documented |
| 11 Oct 2026 | User: agent should review and ask questions; user cannot review line by line | Agent owns audit and proposes decisions in small batches | Architecture, preview and clinical-access questions sent; answers pending |
| 11 Oct 2026 | User: new editable BACS3403_FinalDoc_TanRiLi.docx must match project changes | Current DOCX is authoritative editable report; maintain it alongside approved changes with original backup | File located and inspected read-only; no report edits yet |

No lecturer feedback supplied yet. Suggestions are not automatically authorised changes. For new feedback record affected UI, logic, data/access, tests, effort and verification status.

11 October 2026: user prefers selection cards and asks to avoid two backend codebases. Proposed one shared Python API for both interfaces plus managed Supabase services; single decision card sent. Selection pending. Do not interpret prior "can" as approval of unresolved backend structure, preview scope or privacy rules.

Later 11 October 2026: user said "can" to the single-backend proposal; recorded as approval of one shared Python backend only. Preview selection then explicitly required more functions. Follow-up question asks for their list and real-versus-demo data expectations; answer pending. Privacy rules and complete initial implementation scope remain unapproved. Keeping the turn open allowed a selection response to arrive; continue one question at a time.

Subsequent explicit selections: user requires core function plus appointment booking, patient queue, prescriptions and billing. User approves shared saved records between phone/dashboard, simulated AI/payment processing, and the proposed scoped clinical-access rules. Initial implementation scope/design now approved; hosting/private transfers still need scoped authorisation. Required report alignment recorded in REPORT_REVIEW; DOCX renderer unavailable during preflight, source unchanged.


## Update 11 October 2026 report work deferred

User instructs stopping Word edits for now to save tokens/usage; focus on implementation and revisit report alignment after implementation. Original DOCX hash verified unchanged; prepared draft is not applied or delivered.

11 October 2026: user approved starting shared booking-to-queue work. Local mobile/dashboard/API implemented with synthetic saved records. Six backend tests and TypeScript checks passed; later build/browser results in VERIFY.md, physical phone pending. This is the first increment, not completion of all five preview flows. Word work remains deferred.

11 October 2026: user requests continuing implementation. Prescriptions/dispensing/simulated bills implemented on feature branch, no report edits. Automated checks passed; new browser/phone checks pending because test-process permissions were declined. No new dependencies or hosted services.
