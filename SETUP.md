# Setup

Status: planning only; no app to launch. Do not install packages until initial design approval and first-batch explanation.

Proposed setup: local Node runtime/package manager, Expo mobile app and Next.js dashboard in one repository. No Android Studio required for the initial Expo Go phone demonstration. Versions, commands, ports and configuration will be recorded after scaffolding is approved and verified.

Phone actions after implementation: install Expo Go from Google Play, put phone and computer on the same suitable Wi-Fi, run the project's documented start command, then scan its QR code in Expo Go. [Expo development instructions](https://docs.expo.dev/get-started/start-developing/). Avoid enabling public tunnels without approval. If LAN fails, first check Wi-Fi/client isolation, VPN and firewall; do not disable protections.

Expo Go is a testing host. A separately installable APK requires a later build workflow; Play Store publication is another activity. [Expo FAQ](https://docs.expo.dev/faq/). No builds, accounts or deployments configured.

Later backend: authorised hosted Supabase development project with private storage and versioned migrations; separate stable demo environment when practical. Never put privileged keys in mobile/browser code, docs or Git. No credentials needed for the mocked preview.
