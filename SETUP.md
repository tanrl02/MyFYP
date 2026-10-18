# Setup

Installed locally: Python .venv with FastAPI/uvicorn/httpx; Expo SDK 57, React Native 0.86.3, React 19.2.3, Next.js 16.4.0, TypeScript 5.9. Exact versions: apps/api/requirements.txt and pnpm-lock.yaml. Dependency lifecycle scripts disabled. No Android Studio, hosted database or real login configured.

In MyFYP, double-click in order and leave the three windows open:

1. Start-API.cmd: shared backend port 8000, LAN access for phone.
2. Start-Dashboard.cmd: open http://127.0.0.1:3000.
3. Start-Mobile.cmd: detects computer LAN address and displays Expo QR.

Install Expo Go on Android, use the same private Wi-Fi and scan the QR in Expo Go. Choose Ava Demo or Noah Demo. Ctrl+C stops each service. If a port is occupied, stop the previous project window; do not stop unrelated processes.

Launch scripts prefer the bundled Codex Node/pnpm runtime, otherwise pnpm on PATH. API now uses the existing .venv-ai environment for local photo checks. Install the pinned API/photo-check dependencies and official model as described in [docs/PHOTO_CHECKS.md](docs/PHOTO_CHECKS.md) before launching on another computer. Report scripts are unrelated.

If phone cannot connect, check Wi-Fi/client isolation, VPN and firewall settings; do not disable protections or enable public tunnels. Wrong adapter: set EXPO_PUBLIC_API_URL to http://COMPUTER-LAN-IP:8000 before launching scripts/run-component.ps1 mobile. Dashboard NEXT_PUBLIC_API_URL defaults to http://127.0.0.1:8000. Example environment files contain no secrets.

Saved data: ignored apps/api/data/demo.sqlite3, persists after restart; Git does not back it up. Demo headers are NOT secure login: use synthetic data only on your private network. No private photos uploaded. Expo Go is a testing host; Android JavaScript export is not an APK or physical-device test.

## Current care screens

Dashboard queue page links to /care. Select an assigned doctor to issue, then Staff Demo to dispense/generate bill/record simulated payment. Patient app Care & bills shows the same saved records and supports explicitly confirmed simulated payment. Placeholder items and prices only. Restart the API after pulling code changes; existing SQLite rows are preserved and new tables created automatically. Stop only your old project windows if a port is occupied; do not reset/delete records or stop unrelated processes.

Skin check added: Expo camera/gallery modules installed locally, compatible with SDK57. Restart Expo/API after this update; same QR/LAN address currently applies. Desktop localhost web uses localhost API automatically; Android keeps launcher LAN API. No photo upload goes to external services. Saved images are inside apps/api/data/demo.sqlite3, ignored by Git; preserve that file to keep demonstration history. Microphone permission disabled in image-picker configuration for later native builds; Expo Go host permissions are managed by Expo Go.

18 October: new assessments now run the current selected research checkpoint in the same API. Keep the ignored checkpoint pinned by `apps/api/disease_model.json` available in `.venv-ai`; no extra inference server is needed. See [EXPERIMENTAL_AI.md](docs/EXPERIMENTAL_AI.md) for the patient/doctor flow,59.6% development validation result and limitations. Older assessments stay labelled simulations. Restart the API after updating this code; existing records are migrated without deletion.
