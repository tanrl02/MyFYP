# Setup

Installed locally: Python .venv with FastAPI/uvicorn/httpx; Expo SDK 57, React Native 0.86.3, React 19.2.3, Next.js 16.4.0, TypeScript 5.9. Exact versions: apps/api/requirements.txt and pnpm-lock.yaml. Dependency lifecycle scripts disabled. No Android Studio, hosted database or real login configured.

In MyFYP, double-click in order and leave the three windows open:

1. Start-API.cmd: shared backend port 8000, LAN access for phone.
2. Start-Dashboard.cmd: open http://127.0.0.1:3000.
3. Start-Mobile.cmd: detects computer LAN address and displays Expo QR.

Install Expo Go on Android, use the same private Wi-Fi and scan the QR in Expo Go. Choose Ava Demo or Noah Demo. Ctrl+C stops each service. If a port is occupied, stop the previous project window; do not stop unrelated processes.

Launch scripts prefer the bundled Codex Node/pnpm runtime, otherwise pnpm on PATH. API requires existing .venv. On another computer install locked dependencies/create venv first. Report scripts are unrelated.

If phone cannot connect, check Wi-Fi/client isolation, VPN and firewall settings; do not disable protections or enable public tunnels. Wrong adapter: set EXPO_PUBLIC_API_URL to http://COMPUTER-LAN-IP:8000 before launching scripts/run-component.ps1 mobile. Dashboard NEXT_PUBLIC_API_URL defaults to http://127.0.0.1:8000. Example environment files contain no secrets.

Saved data: ignored apps/api/data/demo.sqlite3, persists after restart; Git does not back it up. Demo headers are NOT secure login: use synthetic data only on your private network. No private photos uploaded. Expo Go is a testing host; Android JavaScript export is not an APK or physical-device test.
