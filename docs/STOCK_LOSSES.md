# Damaged and lost stock

Implemented 19 October 2026 on `feat/stock-loss-recording`.

Staff: Pharmacy stock → Record damaged or lost stock → choose medicine, whole quantity (1–1000), type and required reason (up to 300 characters) → Review stock deduction → Confirm. Keep editing preserves the draft; Cancel discards it. Active and inactive items are supported. The latest 100 saved deductions retain the item label, quantity, type, reason, actual before/after stock, staff identity and timestamp. There is no edit/delete/undo action.

Doctors see the reduced current stock in their prescribing catalogue. Dispensing still checks sufficient stock atomically. Patients use the existing care/billing screens; issued prescription and bill snapshots remain unchanged. Private stock-loss history is staff-only through the stock endpoint.

`POST /stock/losses` requires staff demo identity and a request key. An additive `stock_losses` table stores immutable audit records. A single `BEGIN IMMEDIATE` transaction checks the latest balance, deducts units and saves the record; failures roll back both. Exact retries return the original record even after later movements, and reused keys with changed details conflict. Receiving, competing deductions and dispensing cannot overdraw stock. Catalogue price, status and version are unaffected.

Daily reports include damaged/lost units separately from receiving and dispensing, using Malaysia activity date. These are activity totals, not closing balances. Existing report sections retain their meanings.

Validation: all 187 API tests passed (7 new), mobile TypeScript with Expo types and dashboard production build/TypeScript passed. Tests cover permissions/strict validation, underflow, retries/reopening/frozen labels, existing care snapshots and isolation, inactive items, concurrent movements, audit rollback, additive migration and Malaysia midnight report boundaries.

Browser validation used only the existing fictional medicine `5ccac2e7-a7e9-4581-bb62-d81b39693cd4`: received 5, recorded 2 damaged, final stock 3. Review/Keep editing, excessive quantity disable, Cancel, confirmation and reopening passed. Doctor draft showed 3 units and was cancelled without issuance. Daily report for 19 October shows received 5, damaged/lost 2, dispensed 0. API comparisons confirm other medicines, prior receipts and staff/Ava/Noah care snapshots unchanged. No new medicine, visit, prescription or bill. Evidence: ignored `tmp/stock-loss-before.json`, `tmp/stock-loss-fixture.json`, `tmp/stock-loss-tests.log` and visually inspected `tmp/stock-loss-verified.png`.

No mobile UI change or new Android export; no new physical Android check claimed or requested. Auth, Word, AI/model/training and dependencies unchanged. Preserve the user's unrelated `docs/ai/BASELINE_SETUP.md` edit. No push, deployment or merge. Discuss the next small task before implementation.
