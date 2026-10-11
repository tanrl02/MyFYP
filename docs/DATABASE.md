# Data design

Status: proposed only; no schema, migrations, hosted environment or implemented data access. Final scope retains all nine modules. Reference: report Figure 4.61, PDF 250; permissions in section 4.4 require reconciliation.

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

## Ownership and access proposal

Patients read/update allowed parts of their own profile and see only their authorised records. They cannot assign privileged roles. Doctors see assigned/shared records according to the agreed consent model; authored clinical notes are separate from AI results. Staff receive minimum queue/billing/pharmacy data needed, not blanket clinical access. Admin user operations and report access do not automatically imply unrestricted clinical browsing; final rule pending user discussion.

Private storage must enforce owner/grant access through backend policies. No public image URLs or privileged client credentials. Use migrations for schema/policies; verify cross-user denial, not only successful requests. Stock dispensing/payment updates require atomic/idempotent trusted operations; exact rules await detailed module audit.

Proposed local preview contracts: session id, synthetic patient id, createdAt, image reference, status and prediction origin=`simulation`; ranked label/sample score; separate doctor-review author/body/status/timestamps. Use same field meanings on both UIs but independent local stores. Mobile image paths must be durable, not temporary picker URIs. None implemented.

Migration status: none. Environment: none authorised. Data retention, consent, sharing revocation, admin privileges and record removal are unresolved. Prefer versioned corrections/soft removal over report's permanent deletion, subject to agreement.
