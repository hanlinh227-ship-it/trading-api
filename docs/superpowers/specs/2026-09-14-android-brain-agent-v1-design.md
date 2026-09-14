# ANDROID_BRAIN_AGENT V1 — Design Specification

Date: 2026-09-14
Status: DESIGN FOR USER REVIEW
Base Brain: GITHUB_BRAIN_V4 / capability release 4.8.1
Repository: hanlinh227-ship-it/trading-api
Base main SHA: d14f9a34b6fc06ed1387d5bf170cd733b8a269ac

## 1. Goal

Build a native Android AI agent that runs directly on the phone, can receive high-level goals from GPT/GitHub Brain, observe Android state, plan actions, operate apps through supported Android mechanisms, verify outcomes, retry when needed, and report evidence back to the Brain.

Primary user experience:

`User -> ChatGPT/GitHub Brain -> Android Gateway -> ANDROID_BRAIN_AGENT APK -> observe/plan/act/verify -> result -> Brain -> user`

V1 must not require a PC to remain online.

## 2. Explicit non-goals

The system must not implement or promise:

- concealment of automation from apps;
- anti-cheat, anti-bot or fraud-detection bypass;
- CAPTCHA bypass;
- biometric bypass;
- secure-screen bypass;
- banking/security-control bypass;
- credential theft, OTP extraction, seed/private-key access;
- silent privilege escalation;
- automatic widening of Android permissions without explicit user action.

Apps may detect Accessibility, ADB/Shizuku, automation patterns, instrumentation, overlays, or other signals depending on their implementation. The agent does not attempt to hide these signals.

## 3. Architectural position inside GITHUB_BRAIN_V4

ANDROID_BRAIN_AGENT is a separate execution authority, not a replacement for the Brain router or reasoning authority.

```text
request
  -> task_router
  -> runtime_profile
  -> primary reasoning skill
  -> mobile_automation intent
  -> ANDROID_BRAIN_AUTHORITY
  -> policy gate
  -> signed Android command
  -> device agent
  -> evidence/result
  -> response quality gate
```

The Android executor is a capability provider. It never becomes a parallel reasoning authority.

All imported Android/open-source patterns remain evidence/reference until they pass existing harmonization, provenance, license, security, eval and promotion gates.

## 4. Recommended V1 platform strategy

V1 uses a non-root-first stack:

1. Native Android APK.
2. AccessibilityService for UI tree inspection and supported actions.
3. Android Intents and native platform APIs whenever available.
4. NotificationListenerService for notification-driven workflows.
5. Storage Access Framework for user-authorized file access.
6. WorkManager / foreground services for bounded background execution.
7. MediaProjection only as an explicit user-authorized vision fallback.
8. Optional Shizuku for user-granted ADB-level capabilities when normal APIs are insufficient.
9. No root requirement.

A future dedicated-device edition may support Device Owner provisioning as a separate profile. Root/system-app mode is outside V1.

## 5. High-level component model

```text
GITHUB_BRAIN_V4
    |
    +-- Android Command Adapter
    |      +-- policy classification
    |      +-- device routing
    |      +-- signed command envelope
    |      +-- result normalization
    |
    +-- Android Gateway (cloud)
           +-- pairing registry
           +-- WebSocket/HTTPS command queue
           +-- replay protection
           +-- device presence
           +-- audit metadata
                  |
                  v
ANDROID_BRAIN_AGENT APK
    |
    +-- Agent Runtime
    |      +-- goal interpreter
    |      +-- state machine
    |      +-- planner
    |      +-- verifier
    |      +-- bounded retry/replan
    |
    +-- Perception Layer
    |      +-- accessibility tree
    |      +-- current app/window
    |      +-- notification state
    |      +-- app/package state
    |      +-- screenshot/vision fallback
    |
    +-- Action Layer
    |      +-- native API actions
    |      +-- intents
    |      +-- accessibility node actions
    |      +-- accessibility gestures
    |      +-- optional Shizuku actions
    |      +-- vision-guided gesture fallback
    |
    +-- Skill Layer
    |      +-- android_core
    |      +-- files
    |      +-- browser
    |      +-- messaging adapters
    |      +-- settings
    |      +-- game profiles
    |
    +-- Local State
           +-- approved preferences
           +-- skill metadata
           +-- execution checkpoints
           +-- sanitized history
           +-- pending commands
```

## 6. Agent execution loop

Every autonomous task follows:

```text
GOAL
 -> POLICY CHECK
 -> OBSERVE
 -> BUILD STATE
 -> PLAN NEXT ACTION
 -> EXECUTE ONE BOUNDED ACTION
 -> OBSERVE AGAIN
 -> VERIFY EXPECTED STATE
 -> COMPLETE | RETRY | REPLAN | FAIL CLOSED
```

The agent must not treat a tap or command dispatch as proof of success.

Example:

`send_message(contact, text)` is successful only after the agent observes evidence consistent with the target conversation and sent-message state.

## 7. Perception strategy

Order of preference:

1. Structured Android APIs.
2. Accessibility node tree.
3. App/package and window state.
4. Notifications.
5. MediaProjection screenshot + vision fallback.

Vision is deliberately a fallback because accessibility/native state is cheaper, faster and more deterministic when available.

For games and custom-rendered surfaces where Accessibility exposes little or no semantic UI, a game-specific vision profile may become the primary perception path.

## 8. Action strategy

Action priority:

1. Native Android/API action.
2. Intent/deep link.
3. Accessibility node action.
4. Accessibility global action.
5. Accessibility gesture.
6. Optional Shizuku action.
7. Vision-guided gesture fallback.

Coordinate-only macros are never the default execution model.

Selectors should prefer semantic targets such as package, resource id, text, content description, role and relative layout before raw coordinates.

## 9. Android permission model

### Required/likely V1 permissions and user grants

- INTERNET
- POST_NOTIFICATIONS where required
- Accessibility Service user enablement
- Notification access user enablement for notification workflows
- SYSTEM_ALERT_WINDOW only if assistant overlay is included
- microphone/camera only for explicitly enabled voice/photo features
- Storage Access Framework folder grants for file automation
- foreground-service declarations matching actual service types

### Explicit-session permissions

MediaProjection screen capture must be initiated through Android's user-facing consent flow and handled under the current Android foreground-service rules.

### Optional elevated profile

Shizuku is optional and requires the user to install/activate Shizuku and explicitly grant the agent access. V1 must continue to function in a reduced-capability mode without Shizuku.

## 10. Signed command protocol

Cloud-to-phone control must never accept unauthenticated raw shell text.

Each device owns a device keypair generated on-device. The server stores only the public identity required for verification/routing.

Command envelope:

```json
{
  "schema": 1,
  "command_id": "uuid",
  "device_id": "opaque-device-id",
  "issued_at": "RFC3339",
  "expires_at": "RFC3339",
  "nonce": "random",
  "goal": "normalized high-level goal",
  "capability_scope": ["notifications.read", "apps.open"],
  "risk_class": "A|B|C|D",
  "signature": "detached-signature"
}
```

Device checks before execution:

1. known issuer;
2. valid signature;
3. matching device id;
4. unexpired command;
5. unseen nonce/command id;
6. allowed capability scope;
7. local user policy permits the risk class;
8. required Android permission is currently granted.

Failure of any gate rejects execution.

## 11. Risk policy

### Class A — autonomous

Examples:
- open an app;
- navigate UI;
- read approved notifications;
- search the web;
- organize files inside approved directories;
- inspect device state;
- run a read-only workflow.

### Class B — autonomous with audit

Examples:
- send a normal message to an approved contact;
- upload an approved file;
- change selected low-risk settings;
- create calendar/task data through an approved integration.

Class B must be individually enabled by the user and logged.

### Class C — explicit confirmation

Examples:
- delete significant data;
- publish public content;
- purchase/order a product;
- uninstall apps;
- broad settings changes;
- action with meaningful external consequences.

The agent may prepare the action but must stop at a confirmation gate.

### Class D — protected / no unattended route

Examples:
- money transfer;
- wallet signing;
- banking mutation;
- password/security credential changes;
- OTP/2FA handling as a secret;
- private key/seed extraction;
- disabling device security;
- permission/security bypass.

No autonomous execution path in V1.

## 12. Local memory and privacy

Allowed durable state:

- device capability map;
- skill versions and hashes;
- successful navigation patterns;
- sanitized action outcomes;
- user-approved preferences;
- task checkpoints;
- audit metadata.

Forbidden durable state unless separately designed and explicitly approved:

- raw passwords;
- OTPs;
- private keys/seeds;
- full credential payloads;
- hidden chain-of-thought;
- unrestricted screen recordings;
- raw private application data unrelated to the active task.

Logs should record observable decisions and outcomes, not hidden reasoning.

## 13. App skills

Each app/domain gets an isolated skill contract rather than an unrestricted generic macro.

Proposed V1 skills:

```text
android_core
files
browser
notifications
settings
media
messaging_generic
game_operator
```

App-specific adapters are added only when a generic semantic route is insufficient.

Each skill declares:

- owned intents;
- required Android capabilities;
- selectors/state model;
- permitted actions;
- prohibited actions;
- verification rules;
- risk ceiling;
- recovery strategy;
- test fixtures.

## 14. Game Agent profile

GAME_AGENT is an optional subsystem under Android authority.

Use cases:

- offline/single-player game assistance;
- permitted repetitive tasks;
- strategy observation;
- turn-based/puzzle/building/idle interactions;
- user-directed gameplay where automation is allowed.

Execution model:

```text
screen/frame
 -> game-state detector
 -> profile-specific state
 -> policy/rules
 -> strategy step
 -> tap/swipe/hold
 -> new frame
 -> reward/result verification
```

Each game has a separate GAME_PROFILE containing:

- package id;
- supported screens;
- visual anchors;
- objectives;
- action vocabulary;
- timing ranges;
- failure/recovery states;
- account-risk policy;
- game-specific terms restrictions.

No anti-cheat bypass, input concealment, fingerprint spoofing or detection evasion is permitted.

Online games should default to assistant/read-only mode unless automation is clearly permitted by the service/game rules.

## 15. Self-healing UI automation

When a selector/action fails:

1. refresh the accessibility tree;
2. confirm the foreground package/window;
3. search alternate semantic selectors;
4. retry boundedly;
5. use vision fallback only when allowed;
6. replan the route;
7. fail closed with evidence if confidence remains below threshold.

The agent must never enter an unbounded retry loop.

## 16. Background operation

V1 supports two mechanisms:

### Event-driven

Examples:
- notification received;
- file created/download completed;
- charger connected;
- connectivity changed;
- calendar/time event supplied by an approved integration.

### Scheduled

Use WorkManager for deferrable persistent work and foreground services only when Android rules and the task justify them.

Do not rely on unsupported permanent hidden background execution.

## 17. Cloud gateway

Preferred V1 deployment:

- Cloudflare Worker for authenticated command ingress/routing when compatible with existing Brain runtime;
- state kept minimal and encrypted/opaque where possible;
- WebSocket or bounded polling/FCM-style wake strategy selected during implementation based on Android background reliability;
- no phone-side inbound public TCP port;
- no requirement for the user's PC.

Gateway responsibilities:

- device registration/pairing;
- command authorization metadata;
- short-lived queue;
- replay protection;
- device heartbeat/presence;
- result transport;
- remote kill switch;
- audit metadata.

Gateway must not become a second reasoning authority.

## 18. GPT/Brain integration contract

The Brain exposes a typed provider capability, conceptually:

```text
android.list_devices()
android.get_capabilities(device_id)
android.execute_goal(device_id, goal, requested_scope)
android.get_task(task_id)
android.cancel_task(task_id)
```

Normal chat flow:

```text
User: "Kiểm tra điện thoại xem có thông báo quan trọng nào."
Brain:
  classify -> mobile_automation
  risk -> A
  request android notifications capability
Gateway:
  signed command -> phone
Phone:
  read approved notification state
  summarize structured evidence
Brain:
  verify result -> answer user
```

GPT does not receive unrestricted shell or unrestricted Android RPC by default.

## 19. Open-source reference strategy

Reference candidates:

- ClawDroid / KarakuriAgent: embedded Android agent backend, agent loop, skills, memory, cron, accessibility control.
- Ophoner: native Android AI agent patterns, OpenAI-compatible provider support, SAF-scoped file tools, Shizuku integration.
- Shizuku: optional elevated Android API/shell broker.

Rules:

- verify exact license and commit before reuse;
- prefer architecture/reference extraction over wholesale copying;
- quarantine imported code first;
- dependency/security scan before admission;
- no imported capability can widen Brain authority or Android risk ceiling automatically.

## 20. Reliability targets

V1 design targets:

- deterministic semantic action before coordinate action;
- bounded action loop;
- every material action has a verification condition;
- task state survives app process recreation where feasible;
- rejected/expired commands cannot execute later;
- temporary gateway outage does not corrupt local state;
- permission loss produces a clear degraded-capability result;
- no fabricated task success.

## 21. Test strategy

### Unit tests

- command signature and expiry;
- nonce replay rejection;
- risk classification enforcement;
- selector ranking;
- bounded retry/replan;
- permission/capability checks;
- sanitization of logs.

### Android instrumentation tests

- launch app via intent;
- inspect accessibility tree;
- click semantic nodes;
- gesture fallback;
- notification flow;
- SAF file flow;
- service lifecycle;
- permission revoked while task is active.

### Emulator/device E2E

- Brain/gateway -> phone -> verified result;
- airplane-mode interruption and recovery;
- app UI changed / selector failure;
- screen rotation;
- process kill/restart;
- command cancellation;
- kill switch.

### Security tests

- invalid signature;
- replayed command;
- expired command;
- scope escalation attempt;
- Class C without approval;
- Class D execution request;
- hostile prompt embedded in notification/web/app UI;
- tool output attempting to change policy.

### Game tests

Use only controlled/offline test targets for automated E2E. Validate frame-to-action timing, state recognition and bounded recovery without anti-cheat evasion.

## 22. Proposed repository layout

```text
android_brain_agent/
  README.md
  authority/
    android_authority.yaml
    risk_policy.yaml
    capability_contract.yaml
  gateway/
    schema/
    worker/
  android/
    app/
    core/
    perception/
    actions/
    agent/
    skills/
    game/
    security/
  tests/
    contract/
    android/
    security/
    e2e/

docs/
  android-agent/
    pairing.md
    permissions.md
    integration.md
    troubleshooting.md
```

Existing Brain router/checkpoint remains canonical. Android files do not replace the current V4 authority chain.

## 23. Integration runbook for the user

This is the intended V1 installation experience after implementation.

### Step 1 — install the APK

Install the signed `ANDROID_BRAIN_AGENT` release APK from the project's verified release artifact.

Do not install arbitrary debug builds for daily use.

### Step 2 — pair the phone

Open the agent and select `Pair with Brain`.

The app generates its device keypair locally and displays a one-time pairing QR/code. The cloud gateway registers the public device identity and returns a short-lived pairing confirmation.

No permanent raw API secret should be manually pasted into chat.

### Step 3 — enable core Android permissions

The setup wizard asks only for capabilities selected by the user:

1. Accessibility service;
2. notification access if desired;
3. folder/file access through Android's folder picker;
4. overlay only if the floating assistant is enabled;
5. microphone/camera only if voice/photo features are enabled.

### Step 4 — optional Shizuku

For enhanced system control:

1. install Shizuku from an official trusted distribution;
2. activate it using the Android-supported Shizuku setup path for the device;
3. explicitly grant ANDROID_BRAIN_AGENT access;
4. return to the agent and run `Capability Test`.

The agent must show exactly which extra capabilities became available.

### Step 5 — run read-only diagnostic

Before enabling writes, run:

`Kiểm tra điện thoại và báo các capability hiện có, không thay đổi gì.`

Expected output includes granted/missing capabilities and Android/API constraints.

### Step 6 — run safe action test

Example:

`Mở Chrome, vào một trang thử nghiệm, sau đó quay về màn hình chính.`

The agent must provide a verified completion result.

### Step 7 — enable selected Class B actions

The user chooses which write actions may execute without per-action confirmation. Default is disabled.

### Step 8 — connect GPT/Brain

Once the Android capability provider is deployed, ChatGPT/GitHub Brain routes mobile goals through the typed Android adapter. The user then issues natural-language commands in the normal chat rather than opening a second automation console.

## 24. V1 acceptance criteria

V1 is not complete until all of the following are demonstrated on a real supported Android device:

1. APK installs and runs without PC dependency.
2. Phone pairs cryptographically with the cloud gateway.
3. Brain can query device capability state.
4. Brain can request a Class A task.
5. Agent opens a target app and performs semantic UI actions.
6. Agent verifies the result rather than merely reporting dispatch success.
7. Notification workflow functions when permission is granted.
8. SAF-scoped file workflow functions.
9. Vision fallback works after explicit screen-capture authorization.
10. Optional Shizuku path works when explicitly configured, but V1 remains usable without it.
11. Expired/replayed/invalid commands are rejected.
12. Class C requires confirmation.
13. Class D has no unattended path.
14. Remote kill switch stops new tasks.
15. Logs contain sanitized action/evidence metadata and no secret material.
16. GAME_AGENT can operate a controlled offline test game/profile without detection-evasion features.
17. Exact-source build, tests and release artifact are reproducible/traceable.

## 25. Deferred items

Not required for V1:

- root/system-app build;
- Device Owner edition;
- unrestricted shell from GPT;
- full offline LLM inference on low-end phones;
- cross-device mesh orchestration;
- arbitrary automatic app-skill generation;
- banking/payment automation;
- anti-detection or anti-cheat evasion.

## 26. Design decision summary

Recommended implementation direction:

- native Android APK;
- non-root first;
- Accessibility/native API first;
- vision fallback;
- optional Shizuku;
- signed cloud command protocol;
- Android authority isolated from Brain reasoning;
- user-scoped permissions;
- risk classes with hard protected boundary;
- per-app/per-game skill contracts;
- verification after every material action;
- no PC dependency;
- no automation concealment.

This design intentionally maximizes useful Android autonomy while preserving Android/platform security boundaries and the existing GITHUB_BRAIN_V4 authority model.
