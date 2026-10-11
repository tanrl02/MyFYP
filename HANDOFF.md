# Handoff

Updated 11 October 2026. Word editing/rendering is deferred by user until implementation completes; original report unchanged. Do not resume report QA now.

Approved: all nine final modules; Expo patient Android UI, Next.js dashboard, ONE shared Python backend; Supabase auth/database/private storage planned but no hosted environment selected or accessed. Preview requires skin assessment/history, booking, queue, prescriptions and billing with shared records; AI/payments simulated. Patients see own records; doctors explicit/booking-authorised clinical access; staff minimum operational details; admins no automatic clinical access. Common conditions; no dataset/model; meaningful fine-tuning/evaluation required. Prefer concise updates and one selection card at a time; keep turn active while awaiting answers.

First increment starts from main 87ad49d on feat/booking-queue. apps/mobile, apps/dashboard, apps/api and packages/shared now exist. FastAPI owns transactions; ignored apps/api/data/demo.sqlite3 saves synthetic records across restarts. Demo headers are selectable identities, NOT secure authentication.

Implemented: availability, booking confirmation/retry keys, duplicate/capacity protection, own history, cancellation, queue filters/call-next/completion and shared periodic refresh. Order: appointment time then token; one called patient per doctor/date. Cancellation frees capacity, keeps history/token. Staff can rehearse future clinic dates.

Six API tests and both TypeScript checks passed. Further results in VERIFY.md. Physical Android pending. Camera/AI, prescriptions/billing and real auth are not implemented. Report helper scripts are historical unfinished work, not app features.

Next: finish phone booking/queue checks, then prescription/dispensing/billing tied to saved visits, followed by photo/history with simulated inference. All nine final modules remain required. SETUP.md has launchers. No remote push, deployment, paid service, hosted mutation or private photo upload authorised. Keep synthetic data only. Never claim phone checks, full report audit or model accuracy without evidence. Save local checkpoints after verified increments.
