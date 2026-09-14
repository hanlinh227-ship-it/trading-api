# ANDROID_BRAIN_AGENT V1 — Design Specification

Date: 2026-09-14
Status: APPROVED BY USER — 2026-09-14
Base Brain: GITHUB_BRAIN_V4 / capability release 4.8.1
Repository: hanlinh227-ship-it/trading-api
Base main SHA: d14f9a34b6fc06ed1387d5bf170cd733b8a269ac
Implementation plan: `docs/superpowers/plans/2026-09-14-android-brain-agent-v1.md`

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

The gateway is a separate Android execution service and must not be merged into the trading/live-price runtime.

Responsibilities:

- pair devices using one-time short-lived codes;
- store only public device identity plus sanitized routing metadata;
- deliver signed, scoped, expiring commands;
- reject replay and expired commands;
- track device online/offline/degraded state;
- receive signed result/evidence metadata;
- enforce server-side risk ceilings in addition to on-device policy;
- expose typed mobile-automation tools to approved Brain/GPT integrations.

A device session owns its command queue and live connection. Commands have bounded TTL and queue length.

## 18. Planner/model boundary

The APK does not bundle a user API key or assume that a ChatGPT subscription provides API credentials.

Two execution paths are supported:

1. deterministic skills/state machines for known tasks that do not require model inference;
2. a pluggable cloud planner provider for arbitrary natural-language replanning.

Planner credentials, when configured, remain in approved cloud secret storage. Planner output is treated as untrusted structured input and must pass action schema and risk-policy validation before device execution.

The planner may reduce scope but can never widen the command envelope's capability scope or risk ceiling.

## 19. Typed GPT/connector surface

The gateway exposes typed operations rather than unrestricted shell/control:

- `android_device_status`
- `android_run_goal`
- `android_get_task`
- `android_confirm_action`
- `android_cancel_task`

`android_run_goal` accepts a high-level goal plus a paired device identity. It does not accept raw shell commands.

The connector layer is transport/integration only; it does not become reasoning authority.

## 20. Observability and audit

Record:

- task id;
- device id (opaque);
- command schema/version;
- requested and allowed capability scopes;
- risk class and policy decision;
- timestamps/latency;
- action type and verification result;
- retry/replan counts;
- final status/error code.

Do not persist hidden reasoning, raw credentials, OTPs, unrestricted screen recordings or unrelated private app content.

## 21. Kill switch and degraded mode

The APK exposes a local kill switch that immediately stops queued/new actions and disconnects the command channel.

Degraded states are explicit:

- Accessibility unavailable;
- notification access unavailable;
- Shizuku unavailable;
- vision consent absent/revoked;
- gateway offline;
- planner unavailable.

Unavailable optional capabilities must degrade cleanly rather than crash or silently widen permissions.

## 22. Testing strategy

Required test classes:

- protocol signing/canonicalization/expiry/replay;
- Android policy A/B/C/D;
- semantic selector mapping;
- postcondition verification;
- bounded retry/replan;
- prompt-injection boundary from screen/app content;
- Shizuku absence/degradation;
- MediaProjection consent/revocation;
- game-profile online-default restriction;
- gateway pairing/session/queue/TTL;
- planner risk clamp;
- Brain-provider reasoning-authority separation;
- end-to-end low-risk physical-device acceptance.

No completion claim until APK build, gateway tests/dry-run, Brain canonical validation and one physical device low-risk acceptance test pass.

## 23. Delivery and integration

V1 delivery artifacts:

- Android APK produced by CI;
- separate Android Agent Gateway deployment;
- typed connector/tool contract;
- installation/pairing/security documentation;
- test evidence tied to an exact source SHA.

User onboarding sequence:

1. install the APK;
2. pair with gateway using one-time code;
3. enable Accessibility;
4. optionally enable notification access;
5. grant only chosen SAF folders;
6. optionally activate/grant Shizuku;
7. start vision consent only for tasks that require it;
8. verify CONNECTED/degraded capability state;
9. connect the typed GPT/remote-tool integration;
10. run low-risk acceptance commands before enabling any Class B capability.

## 24. Acceptance criteria

V1 is accepted when:

- no PC is required to remain online;
- signed GPT/Brain-originated Class A goals can reach a paired Android phone;
- the APK can observe, act and verify a low-risk multi-step UI task;
- replay/expiry/signature failures are rejected;
- Class C stops for confirmation and Class D has no unattended path;
- optional permission loss degrades safely;
- GAME_AGENT is profile-bounded and online automation defaults disabled;
- no automation-concealment or security-bypass mechanism exists;
- exact-main CI/deployment evidence and one physical-device acceptance run are available.
