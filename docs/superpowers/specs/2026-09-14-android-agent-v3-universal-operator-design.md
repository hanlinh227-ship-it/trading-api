# Android Brain Agent V3 Universal Operator — Design

**Date:** 2026-09-14  
**Status:** Approved by standing user authorization for immediate implementation  
**Target:** Single sideloaded Android APK + existing Cloudflare gateway  
**Baseline:** Android Brain Agent V2.4 (`0.2.4-alpha`, versionCode 8)

## 1. Goal

Upgrade V2.4 from a fixed command parser into a bounded general-purpose Android GUI agent that can execute arbitrary multi-step tasks on ordinary, user-accessible Android application surfaces by repeatedly observing the device, planning one typed action, executing it, verifying the resulting state, and recovering when an action does not achieve the intended effect.

“Universal” means broad control of normal app UI reachable under permissions the user explicitly grants. It does **not** mean bypassing Android security boundaries. The agent must fail closed on lock-screen authentication, biometrics, OTP/2FA secrets, `FLAG_SECURE` content, wallet signing, banking/financial mutation, permission/security bypass, or any surface the platform intentionally withholds.

## 2. Research basis

The architecture follows the common pattern used by modern mobile GUI agents and Android’s supported automation primitives:

- Android Accessibility can retrieve interactive window/node trees, perform gestures, and, when declared, take screenshots on supported API levels.
- Accessibility screenshots are preferable to a persistent MediaProjection dependency for this product because recent Android versions require explicit projection consent for each capture session.
- Modern mobile agents such as Droidrun/Mobilerun combine semantic accessibility state with screenshots, typed tap/swipe/type actions, multi-step planning, and execution traces.
- GUI-agent work such as UI-TARS treats coordinate grounding and mobile-specific actions (`open_app`, `long_press`, `press_home`, `press_back`) as first-class primitives.
- Cloudflare Workers AI supports vision models, structured JSON output, and function/tool calling. The gateway can therefore host a bounded cloud planner without adding a local model or local server requirement.

Reference documentation:
- https://developer.android.com/reference/android/accessibilityservice/AccessibilityService
- https://developers.cloudflare.com/workers-ai/features/json-mode/
- https://developers.cloudflare.com/workers-ai/models/llama-3.2-11b-vision-instruct/
- https://github.com/appwiz/droidrun
- https://github.com/bytedance/UI-TARS

## 3. Non-goals and hard boundaries

V3 must not:

- root the phone, unlock the bootloader, or require ADB/Shizuku for normal operation;
- bypass lock screen, biometrics, secure-window screenshot restrictions, enterprise policy, or Android permission prompts;
- extract or expose passwords, PINs, OTP/2FA secrets, private keys, recovery phrases, authentication cookies, or banking credentials;
- sign wallets, transfer money/crypto, place financial orders, mutate banking state, or silently widen Class-D authority;
- publish raw screenshots, SMS bodies, contact lists, or private UI trees to public GitHub Actions logs;
- report success merely because a command was queued. Device execution and task postconditions remain separate states.

## 4. Architecture

### 4.1 Device-side layers

#### ObservationEngine
Produces a rich but policy-filtered `DeviceObservation`:

- foreground package/window title;
- semantic accessibility nodes with ephemeral IDs, resource ID, role/class, non-secret text/description, bounds, enabled/clickable/long-clickable/editable/scrollable/checkable/checked/selected/focused state;
- screen dimensions and timestamp;
- optional compressed screenshot captured by `AccessibilityService.takeScreenshot()` where Android permits it;
- a deterministic observation fingerprint for no-op/repetition detection.

Password nodes are always redacted. Screenshot bytes are ephemeral and never written to public logs.

#### ActionEngine
Typed actions replace free-form UI instructions as the primary execution contract:

- `launch_app(packageName)`
- `open_url(url)`
- `tap_node(nodeId)` / `long_press_node(nodeId)`
- `tap(x,y)` / `long_press(x,y,durationMs)` / `double_tap(x,y)`
- `swipe(startX,startY,endX,endY,durationMs)`
- `scroll_node(nodeId,direction)`
- `set_text(nodeId,value)` / `clear_text(nodeId)`
- `global_back`, `global_home`, `global_recents`, `global_notifications`, `global_quick_settings`
- `wait(durationMs)`
- `observe`

Node-first execution is preferred over coordinates. Coordinate actions are a visual fallback.

#### LocalResolvers
Deterministic device-local helpers for data that should not be exported merely for reasoning:

- Contacts resolver via `ContactsContract` when `READ_CONTACTS` is granted;
- installed/launchable app resolver;
- notification state via the existing notification listener;
- later file helpers through user-granted Android storage access.

Unknown-number SMS cleanup must compare visible sender numbers to contacts on-device whenever possible. A conversation is never classified as “unknown” merely because a cloud model guesses it.

#### TaskSessionEngine
Runs a bounded state machine:

`OBSERVING -> PLANNING -> ACTING -> VERIFYING -> (RECOVERING | COMPLETED | FAILED)`

Rules:

- one action per planning step;
- re-observe after each action;
- maximum 40 actions per task by default;
- maximum 5 consecutive recovery attempts;
- detect repeated observation fingerprints/no-op loops;
- stop immediately on risk escalation, secure/sensitive state, stale task, kill switch, or explicit cancellation.

### 4.2 Gateway-side layers

#### Task API
Preserve V2 `/commands` for backward compatibility and add a high-level task path:

- `POST /v1/device/:deviceId/tasks`
- `GET /v1/device/:deviceId/tasks/:taskId`
- device observations/results continue through authenticated device-only endpoints.

The gateway stores active task state in the existing per-device Durable Object.

#### Planner
A planner receives:

- original user goal;
- allowed capability scope and immutable risk ceiling;
- current observation tree summary;
- optional current screenshot;
- bounded recent step history.

It returns exactly one structured action plus expected postcondition and a short machine-readable rationale code. It never directly executes actions.

Primary cloud planner target: Workers AI vision model with structured JSON output. First implementation targets `@cf/meta/llama-3.2-11b-vision-instruct` because Cloudflare documents vision input and JSON Mode for it. The deployment must tolerate model unavailability/license activation by falling back to deterministic planning for supported simple actions and reporting degraded planner state rather than fabricating autonomy.

#### Policy clamp
Every planner output is validated against:

- typed action schema;
- signed task/device identity;
- original capability scope;
- immutable task risk ceiling;
- current Class-C confirmation state;
- hard Class-D deny list.

A planner cannot grant itself a capability or escalate risk.

## 5. Protocol

V3 introduces command schema 2 for typed actions while retaining schema 1 parsing during migration.

Schema-2 signed command fields:

- `schema: 2`
- existing identity/time/nonce fields;
- `taskId`
- `action: TypedAction`
- `capabilityScope`
- `riskClass`
- signature over canonical deterministic JSON/action representation.

The Android client verifies the signature and device ID before dispatch.

Task observations are uploaded through the device-authenticated channel, never GitHub issues. Public CI/status logs expose only sanitized task state (`QUEUED`, `DEVICE_EXECUTED`, `COMPLETED`, `FAILED`, error code, step count), not private observation payloads.

## 6. Permission model

V3 may request only capabilities needed for the operator:

- Accessibility service: retrieve window content, perform gestures, take screenshots;
- `READ_CONTACTS` for local contact matching;
- notification access remains an explicit Android user grant;
- storage access is added only through Android’s supported user-granted storage mechanisms when file automation is implemented.

The APK remains usable when optional permissions are denied; relevant capabilities degrade explicitly.

## 7. Risk model

Risk classes remain monotonic:

- **A:** observe, navigate, launch/open, scroll, back/home, other non-mutating UI navigation.
- **B:** typing, drafting, non-destructive app state changes. V3 gateway may enable B only after explicit scoped policy tests.
- **C:** delete, publish/post/send, purchase, irreversible/destructive mutations. Requires explicit confirmation bound to the original task.
- **D:** credentials/OTP/private-key/security-bypass/financial transfer or signing actions. Always denied unattended.

The effective risk of a step is `max(task risk, action risk, policy classifier risk)`; no component may downgrade it.

## 8. Privacy

- Password nodes have text/description removed before observation serialization.
- Sensitive-field heuristics redact likely OTP/password/PIN/secret/recovery inputs even if an app mislabels them.
- Screenshot capture is skipped or rejected for known secure/sensitive surfaces.
- Screenshot/image payloads are transient task inputs and never included in `lastResult.detail`, GitHub issue bodies, Actions logs, or long-lived audit output.
- Contact matching should occur locally; cloud planner receives only the minimum semantic result needed for the action.

## 9. Unknown-number Messages use case

Acceptance scenario:

1. Open the device’s Messages app.
2. Observe the conversation list.
3. For each visible conversation whose sender is a phone-number-like value, normalize it locally and query `ContactsContract`.
4. Keep named/saved contacts and service senders that cannot be deterministically classified.
5. Select only conversations whose visible number is confirmed absent from Contacts.
6. Scroll and continue with bounded deduplication until all reachable conversations have been assessed.
7. Before destructive deletion, require the already-explicit Class-C task confirmation.
8. Delete selected conversations and verify the resulting list no longer contains the selected conversation identities.
9. If any screen/layout ambiguity prevents deterministic identification, stop that item rather than deleting it.

No direct SMS-provider database mutation is required; V3 operates through the user-visible app UI unless the app is explicitly made the default SMS handler in a separate future design.

## 10. Failure/recovery behavior

Recoverable examples:

- target node moved: re-observe and re-ground;
- node exists but is not clickable: try nearest actionable ancestor;
- semantic target absent: use screenshot grounding if allowed;
- transient dialog: planner handles the dialog as the next observed state;
- action no-op: re-observe, increment retry count, choose an alternate primitive;
- app changed unexpectedly: return to expected app only if task policy allows.

Fail-closed examples:

- secure screenshot denied;
- required optional permission missing;
- Class-C confirmation absent;
- Class-D action inferred;
- repeated no-op/recovery loop;
- planner/model unavailable and deterministic fallback cannot safely continue.

## 11. Versioning and compatibility

- V3 versionCode: **9**
- V3 versionName: **`0.3.0-alpha`**
- Same application ID/signing identity so update-in-place preserves pairing where Android permits.
- Existing schema-1 command path remains supported for opening apps and legacy basic navigation during rollout.
- Gateway `/health` reports planner mode/capabilities without exposing secrets.

## 12. Acceptance criteria

V3 is not ready until all are true:

1. Existing V2.4 tests and open-app physical path do not regress.
2. Accessibility screenshot capability is declared and a screenshot provider is implemented for API 30+ with explicit unsupported/error states.
3. Rich semantic observations include bounds/actionability but redact password/sensitive text.
4. Typed coordinate tap, long press, double tap, scroll, text, wait, and supported global actions exist.
5. Schema-2 typed commands are signed and verified; schema 1 stays compatible.
6. Task loop implements observe/plan/act/verify/recover with step/retry limits and no-op detection.
7. Gateway policy clamp rejects capability/risk escalation and all Class-D actions.
8. Private screenshots/raw message/contact content never appear in public GitHub workflow logs or status summaries.
9. Contacts resolver can deterministically answer whether a normalized phone number exists when permission is granted.
10. Unknown-number SMS cleanup has a deterministic local selection path and destructive confirmation gate.
11. Android unit tests, gateway tests, dry-run/deploy checks, and post-merge production verification all pass.
12. A V3 debug APK artifact is built and installable before readiness is reported.
