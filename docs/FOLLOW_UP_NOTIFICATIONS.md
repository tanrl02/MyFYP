# Follow-up recommendation notifications

Implemented 18 October 2026. Doctor follow-up recommendations now create an in-app patient notification in the same transaction. Existing recommendation dates, booking rules and consent remain unchanged.

Doctor: Consultation notes -> assigned called/completed visit -> Recommend a follow-up visit -> Review -> Confirm. Patient: Notifications -> Follow-up visit recommended -> Open visit -> original visit details -> review the reason and choose/confirm a follow-up time. Back to Notifications and persistent Read state reuse the existing flow. Staff sees the confirmed booking in the shared queue, without the recommendation reason.

The new `follow_up_recommended` kind uses the original booking as source and target. Copy contains the assigned doctor, original visit token/date/time and earliest follow-up date in Malaysia time, but no clinical reason, photo or findings. The date means on or after, not a reserved appointment. Nothing is booked until the patient confirms a time.

The existing unique patient/kind/source key and serialized transaction prevent duplicates. Exact recommendation retries return the saved recommendation without creating another alert or resetting Read. Notification failure rolls back the recommendation. Previously saved recommendations are not backfilled, including when retried. Historical alerts remain after a follow-up is booked/cancelled; Open visit always loads the latest recommendation and booking status. No push, email, reminders worker, new schema or dependencies.

Verification:114 API tests passed (four new tests for content/roles/ownership, concurrent retries/read/restart/history, atomic rollback, and legacy/non-authorized inputs); both workspace TypeScript checks and Android Hermes export passed. Dashboard UI is unchanged, so no new dashboard production build was needed.

Browser verified doctor confirmation -> Ava notification -> correct original visit -> follow-up booking on29Oct9am -> Back to Notifications -> Read retained after reload; Noah has no Ava alert. Shared staff queue read confirmed the new waiting booking and excluded its reason. Own synthetic source `52f5882a-6863-4ab9-917d-d712d07d1960` (Ava/L00128Oct9am), follow-up `867db60f-0238-4b20-9801-b07ae652844d` (Lim/L00129Oct9am), notification `7d11f3c5-952f-4596-bf8e-62d5f6b4b3f3` marked Read. No pre-existing user visit modified. Evidence: `tmp/follow-up-notification-fixture.json`, `tmp/follow-up-notification-verified.png`. User confirmed Android on18October: correct original visit and linked follow-up, Back to Notifications, Read after reopening and Noah separation all work. The pending physical check is resolved.

API restarted: session85301 PID82948 port8000, `.venv-ai`; existing dashboard17348/3000 and Expo28048/8081 retained. Word, real auth, AI/model/training, dependencies and user's `docs/ai/BASELINE_SETUP.md` edit remain unchanged. No push/deployment/main merge.
