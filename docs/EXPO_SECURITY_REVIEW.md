# Expo CLI dependency review

Checked 25 October 2026 against the npm registry and linked advisories.

**Both findings remain unresolved. No compatible published update was available.**

The app already uses the latest published SDK 58 package, `expo@58.0.19`, resolving `@expo/cli@58.1.15`. The CLI requires `node-forge@^1.4.0` and `zod@^3.25.76`; `@expo/code-signing-certificates` also requires `node-forge@^1.4.0`.

| Dependency | Installed | Published fix | Result |
| --- | --- | --- | --- |
| node-forge | 1.4.0 | None listed; latest published is 1.4.0 | Await a patched release and compatible Expo dependency resolution |
| zod | 3.25.76 | 4.6.6 or later; latest v3 remains 3.25.76 | Await an Expo-supported migration or compatible patched v3 release |

The production dependency audit reports **two high findings, zero critical**. Every reported path runs through the mobile app's Expo CLI dependencies. The dashboard's earlier Next.js findings remain cleared by `next@16.4.3`.

This dependency-path review does not establish exploitability or prove the findings harmless. Expo Doctor checks project compatibility; passing it does not clear security advisories.

No package, lockfile, override, audit exclusion, signing configuration or security policy was changed. In particular, the Zod v4 fix was not forced into Expo's v3 dependency range, and no unreviewed cryptographic patch was introduced.

## Recheck when upstream publishes a fix

From the project root, using the installed pnpm runtime:

```powershell
pnpm view expo@58 version
pnpm view '@expo/cli@58' version
pnpm view node-forge dist-tags
pnpm view zod dist-tags
pnpm audit --prod --json
```

Check the actual Expo CLI and signing-certificate dependency ranges before updating. After a compatible fix is installed, verify resolved versions and audit paths, then run Expo's dependency check, Expo Doctor, workspace TypeScript, and Android/web exports. Do not treat a successful build as remediation evidence.

## Sources

- [node-forge advisory GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv)
- [Zod advisory GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)
- [Expo SDK 58 CLI dependency manifest](https://github.com/expo/expo/blob/sdk-58/packages/%40expo/cli/package.json)
- [Open Expo remediation discussion](https://github.com/expo/expo/issues/51773) (an issue report, not maintainer-approved remediation)

Local ignored evidence: `tmp/expo-security-*-registry.json`, `tmp/expo-security-*-versions.json`, `tmp/expo-security-cli-dependencies.json`, `tmp/expo-security-audit.json`, and Expo check/Doctor logs. No monitoring or automatic follow-up was scheduled.
