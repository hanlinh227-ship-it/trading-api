# Android Brain Agent V3 Universal Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing single-APK Android Brain Agent into a bounded observe-plan-act-verify-recover operator for normal Android UI while preserving signed commands, risk ceilings, privacy, and V2 compatibility.

**Architecture:** The Android APK produces a rich sanitized accessibility observation plus optional ephemeral screenshot, executes typed node/coordinate/system actions, and verifies post-action state. The Cloudflare Durable Object gateway owns high-level task state and a bounded Workers AI planner; planner output is schema-validated and clamped to the original task’s capabilities/risk before a typed signed action reaches the phone.

**Tech Stack:** Kotlin/Android AccessibilityService, ContactsContract, OkHttp/WebSocket, JUnit 4, Cloudflare Workers/Durable Objects, JavaScript, Workers AI, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-14-android-agent-v3-universal-operator-design.md`

## Global Constraints

- Android `minSdk = 26`, `compileSdk = 35`, `targetSdk = 35`.
- V3 `versionCode = 9`, `versionName = 0.3.0-alpha`.
- No root, ADB, Shizuku, OEM unlock, security/biometric/lock bypass, OTP/2FA extraction, wallet signing, or financial mutation.
- Password/secret content must never enter cloud observations or public logs.
- Screenshots are ephemeral task inputs only; never GitHub issue/log/status payloads.
- Schema 1 commands remain compatible while schema 2 adds typed actions.
- Effective risk is monotonic; Class C requires explicit confirmation, Class D is denied.
- Every planner action is one step followed by a fresh observation and verification.
- Default task limits: 40 actions, 5 recovery attempts.

---

### Task 1: Rich observation model and sensitive-data redaction

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/AccessibilitySnapshot.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/BrainAccessibilityService.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/ObservationSanitizer.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/AccessibilitySnapshotTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/ObservationSanitizerTest.kt`

**Interfaces:**
- Produces: `DeviceObservation`, `ObservedNode`, `ObservationSanitizer.sanitizeText(...)`, deterministic `fingerprint()`.
- Consumes: current accessibility node tree.

- [ ] **Step 1: Write failing unit tests** asserting that observations retain bounds/actionability/editability/scrollability, generate stable ephemeral node IDs for a snapshot, fingerprint equal semantic states identically, and strip password/PIN/OTP/secret/recovery text.
- [ ] **Step 2: Run `cd android-brain-agent && ./gradlew testDebugUnitTest` and confirm RED** due to missing observation types/sanitizer.
- [ ] **Step 3: Implement focused observation types and sanitizer**. Node IDs must be deterministic within a snapshot (tree path or indexed traversal), not durable identifiers. Add raw fields `longClickable`, `editable`, `scrollable`, `checkable`, `checked`, `selected`, `focused`, and `visibleToUser`.
- [ ] **Step 4: Update `BrainAccessibilityService.snapshot()`** to collect the richer fields while never collecting password text into the sanitized type.
- [ ] **Step 5: Run Android unit tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): add rich sanitized observations`.**

### Task 2: Accessibility screenshot capability and ephemeral image capture

**Files:**
- Modify: `android-brain-agent/app/src/main/res/xml/accessibility_service_config.xml`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/AccessibilityScreenshotProvider.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/BrainAccessibilityService.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/ScreenshotPolicyTest.kt`

**Interfaces:**
- Produces: `ScreenshotCapture` sealed result (`Captured`, `Unsupported`, `Denied`, `Failed`) and `captureScreenshot(callback)`.
- Consumes: Android API 30+ `AccessibilityService.takeScreenshot`.

- [ ] **Step 1: Write failing screenshot policy tests** proving API <30 is unsupported, secure/sensitive package policy can deny capture, and raw bytes are never represented by `toString()`/status summaries.
- [ ] **Step 2: Run Android unit tests and confirm RED.**
- [ ] **Step 3: Add `android:canTakeScreenshot="true"`** to accessibility metadata while preserving existing retrieve-window/gesture capabilities.
- [ ] **Step 4: Implement screenshot provider** using `takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, TakeScreenshotCallback)` on API 30+, converting `HardwareBuffer` safely to a compressed in-memory image and closing resources. Do not persist to disk.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): add ephemeral accessibility screenshots`.**

### Task 3: Typed V3 action model and universal action engine

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/Action.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/NodeLocator.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/action/NodeLocatorTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/protocol/TypedActionTest.kt`

**Interfaces:**
- Produces typed actions: `TapPoint`, `LongPressPoint`, `DoubleTapPoint`, `ScrollNode`, `ClearText`, `Wait`, global recents/notifications/quick-settings, plus existing actions.
- `NodeLocator` maps ephemeral observation node ID to current `AccessibilityNodeInfo` using traversal path/ID.

- [ ] **Step 1: Write failing tests** for JSON/type mapping and deterministic node lookup independent of fuzzy text matching.
- [ ] **Step 2: Run unit tests and confirm RED.**
- [ ] **Step 3: Implement typed action data classes and explicit risk classes.** `SetText`/`ClearText` remain B; navigation/observation actions A; destructive action is never inferred as A.
- [ ] **Step 4: Extend AccessibilityActions** with coordinate tap/long press/double tap, node scroll forward/backward, clear text, wait, and supported Android global actions. Keep text-selector actions for schema-1 compatibility.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): add typed universal UI actions`.**

### Task 4: Schema-2 signed typed command protocol

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/CommandEnvelope.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/CommandDispatcher.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/TypedActionCodec.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/protocol/CommandEnvelopeV2Test.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/protocol/TypedActionCodecTest.kt`

**Interfaces:**
- Schema 1: existing `goal` behavior unchanged.
- Schema 2: `taskId: String`, `action: TypedAction`, signature canonicalization includes deterministic action JSON.

- [ ] **Step 1: Write RED tests** for schema-1 compatibility, schema-2 parse/signature bytes, malformed typed action rejection, wrong-device rejection, and capability scope rejection.
- [ ] **Step 2: Run tests and confirm RED.**
- [ ] **Step 3: Implement backward-compatible envelope model/codec** with deterministic ordered action representation.
- [ ] **Step 4: Update dispatcher** so schema 2 bypasses free-form `GoalParser`, runs the same risk policy, dispatches typed actions, and returns sanitized post-action observation metadata only.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): support signed schema-2 typed actions`.**

### Task 5: Local contacts resolver and deterministic unknown-number classification

**Files:**
- Modify: `android-brain-agent/app/src/main/AndroidManifest.xml`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/local/PhoneNumberNormalizer.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/local/ContactsResolver.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/core/UnknownNumberConversationClassifier.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/local/PhoneNumberNormalizerTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/skills/core/UnknownNumberConversationClassifierTest.kt`

**Interfaces:**
- `PhoneNumberNormalizer.normalize(raw, defaultCountry = "VN"): String?`
- `ContactsResolver.isSavedNumber(number): ContactMatch` where result is `Saved`, `NotSaved`, or `PermissionUnavailable`.
- classifier only returns `UnknownConfirmed` when a phone-like sender is visible and resolver says `NotSaved`.

- [ ] **Step 1: Write RED tests** for Vietnamese `0xxxxxxxxx`, `+84`, separators, non-phone service IDs, and permission-unavailable fail-closed behavior.
- [ ] **Step 2: Run tests and confirm RED.**
- [ ] **Step 3: Add `READ_CONTACTS` manifest permission** without forcing it at startup.
- [ ] **Step 4: Implement resolver and classifier**; never classify names/alphanumeric service senders as unknown numbers.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): add local unknown-number resolver`.**

### Task 6: Gateway typed task/session state and risk clamp

**Files:**
- Modify: `android-agent-gateway/src/tools.js`
- Modify: `android-agent-gateway/src/device-session.js`
- Modify: `android-agent-gateway/src/index.js`
- Create: `android-agent-gateway/src/task-policy.js`
- Create: `android-agent-gateway/src/action-schema.js`
- Test: `android-agent-gateway/test/task-policy.test.js`
- Test: `android-agent-gateway/test/task-session.test.js`
- Test: `android-agent-gateway/test/index.test.js`

**Interfaces:**
- `validateTypedAction(input)` returns normalized action or throws.
- `clampTaskStep({task, action})` rejects capability/risk escalation and D actions.
- New control endpoints `POST /v1/device/:id/tasks`, `GET /v1/device/:id/tasks/:taskId`.
- Device DO stores task goal, risk ceiling, confirmation state, step count, recovery count, last fingerprint, status.

- [ ] **Step 1: Add RED gateway tests** for task creation, status lookup, max-step/recovery limits, Class-C confirmation binding, Class-D deny, and planner capability escalation rejection.
- [ ] **Step 2: Run `cd android-agent-gateway && npm test` and confirm RED.**
- [ ] **Step 3: Implement action schema and task policy clamp.**
- [ ] **Step 4: Extend Durable Object task storage/endpoints** while retaining existing queue/result behavior.
- [ ] **Step 5: Extend `/health`** with `taskSchema: 2`, `plannerMode`, and privacy-safe capability flags.
- [ ] **Step 6: Run gateway tests and confirm GREEN.**
- [ ] **Step 7: Commit `feat(android-agent-gateway): add bounded V3 task sessions`.**

### Task 7: Workers AI visual planner with deterministic fallback

**Files:**
- Modify: `android-agent-gateway/wrangler.jsonc`
- Replace/expand: `android-agent-gateway/src/planner.js`
- Create: `android-agent-gateway/src/planner-schema.js`
- Test: `android-agent-gateway/test/planner.test.js`

**Interfaces:**
- `planNextStep({env, task, observation, imageDataUrl})` returns `{action, expected, mode}`.
- Planner target: `@cf/meta/llama-3.2-11b-vision-instruct` with JSON schema response where available.
- Deterministic fallback handles legacy/open/back/home/known safe controls only and never pretends to be vision-capable.

- [ ] **Step 1: Write RED tests** with a fake `env.AI` asserting planner prompt omits secrets, output is schema-validated, invalid model action is rejected/clamped, and AI failure yields explicit deterministic fallback/degraded status.
- [ ] **Step 2: Run gateway tests and confirm RED.**
- [ ] **Step 3: Add Workers AI binding**: `"ai": { "binding": "AI" }`.
- [ ] **Step 4: Implement structured planner** with minimum observation context, optional ephemeral screenshot, one action per call, and bounded recent history.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent-gateway): add bounded visual planner`.**

### Task 8: Device task-loop integration and observe-act-verify-recover

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskSessionEngine.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskProgress.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/AgentConnectionManager.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/TaskSessionEngineTest.kt`

**Interfaces:**
- `TaskSessionEngine.next(observation, previousResult)` enforces 40-step/5-recovery/no-op limits.
- Gateway client posts sanitized observations/task step results over device-authenticated endpoints.
- Existing command queue remains push-first WebSocket.

- [ ] **Step 1: Write RED state-machine tests** covering happy path, repeated fingerprint no-op, recoverable failure, retry exhaustion, kill switch, Class-C confirmation missing, and completion.
- [ ] **Step 2: Run Android tests and confirm RED.**
- [ ] **Step 3: Implement state engine and network methods** with screenshot payload sent only in the device-authenticated planner path and never in normal result detail.
- [ ] **Step 4: Integrate push-first execution** without increasing the 350ms fallback cadence or blocking foreground-service responsiveness.
- [ ] **Step 5: Run tests and confirm GREEN.**
- [ ] **Step 6: Commit `feat(android-agent): add observe-act-verify-recover loop`.**

### Task 9: V3 packaging, regression, privacy audit, and deployment

**Files:**
- Modify: `android-brain-agent/app/build.gradle.kts`
- Modify tests/workflow only if verification exposes a real defect.

**Interfaces:**
- APK reports versionCode 9 / `0.3.0-alpha`.
- Gateway production reports V3 task capability only after deployment verification.

- [ ] **Step 1: Set versionCode 9 and versionName `0.3.0-alpha`.**
- [ ] **Step 2: Run complete Android test/build:** `cd android-brain-agent && ./gradlew testDebugUnitTest assembleDebug`.
- [ ] **Step 3: Run complete gateway verification:** `cd android-agent-gateway && npm test && npx wrangler deploy --dry-run`.
- [ ] **Step 4: Search generated logs/source paths for accidental screenshot/base64/SMS/contact dumps; fail if private observation content is publicly logged.**
- [ ] **Step 5: Open PR and require all repository CI jobs green.**
- [ ] **Step 6: Merge only after verification, then verify production gateway `/health`/source SHA and command compatibility.**
- [ ] **Step 7: Download the CI-built V3 APK artifact, compute SHA256, and provide the APK to the user.**
- [ ] **Step 8: Run a physical non-destructive smoke test first: open Messages, observe, Back/Home. Only after that test destructive workflows with the user’s explicit Class-C authorization.**
