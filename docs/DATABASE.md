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
