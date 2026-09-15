# Unified Adaptive Android Brain V5 — Design

**Date:** 2026-09-15  
**Status:** User-approved architecture; written-spec review gate pending  
**Target release:** Android Brain Agent `0.5.0` / proposed versionCode `14`  
**Baseline:** Android Brain Agent V4 Universal Operator on `main`  
**Primary objective:** One unified, low-latency Android operator that continuously observes, reasons, acts, verifies, learns app structure, and escalates reasoning only when needed without exposing separate A/B modes to the user.

---

## 1. Product intent

V5 upgrades Android Brain Agent from a cloud-coordinated multi-step operator into a **Unified Adaptive Android Brain**.

The user should be able to express ordinary goals such as:

- “Open this app and finish the setup.”
- “Clean this inbox until there is nothing unnecessary left.”
- “Play this game until I tell you to stop.”
- “Find the setting I asked for and change it.”
- “Learn how this app works so you can do this faster next time.”

The system must operate through one execution loop:

```text
request
  -> Unified Intent
  -> Unified Observation
  -> Dynamic Inference Budget
  -> Unified Planner
  -> Unified Executor
  -> Unified Verifier
  -> Memory / App Map update
  -> continue
```

There is **no user-visible Fast mode, Smart mode, A mode, B mode, game mode, or cloud mode**. The operator is one system. It automatically uses the cheapest sufficient reasoning path for the current state.

The desired behavior is:

- obvious operations execute locally with minimal delay;
- complex or ambiguous states receive deeper reasoning automatically;
- cloud reasoning is an extension of the same planner, not a separate operating mode;
- repeated verified workflows become faster through app-scoped memory;
- long-running tasks persist until their actual stop condition is met;
- UI changes cause re-grounding and recovery rather than blind replay;
- safety policy remains monotonic and cannot be learned away.

“Universal” means broad operation of ordinary user-accessible Android UI under permissions explicitly granted by the device owner. It does not mean root, security bypass, hidden privilege escalation, CAPTCHA bypass, biometric bypass, credential extraction, OTP handling for unattended execution, wallet signing, or other prohibited Class-D actions.

---

## 2. Problems V5 must solve

V4 established task-first execution, long-horizon sessions, visual fallback, deterministic skills, WebSocket control, typed actions, and app-scoped skill memory. The remaining bottlenecks are architectural.

### 2.1 Per-step cloud latency

Many task steps still follow a loop similar to:

```text
device observes
 -> uploads observation
 -> gateway plans
 -> device receives next action
 -> device executes
 -> repeat
```

This is robust but unnecessarily slow for obvious actions such as a known tap, swipe, Back, menu transition, familiar screen path, or deterministic game move.

### 2.2 Perception work is more expensive than necessary

A full screenshot and full planner round-trip are not required for every state change. Android Accessibility events already provide a low-latency event stream for many apps. Screenshots should be used selectively for Canvas, WebView, custom rendering, visual ambiguity, and verification where semantic information is insufficient.

### 2.3 App knowledge is shallow

An app cannot be represented as a single package name or one fixed macro. A real app contains many screens, dialogs, tabs, states, data-dependent variants, A/B variants, and version-specific layouts.

The system needs a living graph of:

```text
AppProfile
 -> ScreenGraph
 -> ElementGraph
 -> TransitionGraph
 -> VerifiedSkills
 -> RecoveryPatterns
```

### 2.4 Long-running sessions need real persistence semantics

A task such as “play until I tell you to stop” must not terminate because it reached an arbitrary 900- or 1000-action budget. Step budgets should remain safety and checkpoint controls, not ordinary terminal conditions for explicitly persistent sessions.

### 2.5 Verification must work for semantic and visual-only interfaces

Canvas/WebView/game state may change while the Accessibility tree remains identical. V5 must treat semantic fingerprints, visual fingerprints, app/window state, and skill-specific state as distinct verification channels.

---

## 3. Design principles

### 3.1 One engine, adaptive reasoning

V5 has one `UnifiedOperatorEngine`. It does not switch between separate user-visible modes.

For each decision it computes a `DynamicInferenceBudget` from:

- current confidence;
- app familiarity;
- screen familiarity;
- semantic-tree completeness;
- visual uncertainty;
- task complexity;
- action reversibility;
- risk class;
- recent execution failures;
- expected latency cost;
- whether a verified local recipe already exists.

The budget controls how much perception and reasoning are required before acting.

### 3.2 Local-first action, cloud-augmented reasoning

Local execution is preferred when the action is sufficiently grounded and safe. Cloud reasoning is invoked only when it materially improves correctness.

This is not a local-vs-cloud mode switch. The same task state and the same planner contract continue through escalation and return.

### 3.3 Verify before learning

Only verified successful transitions can strengthen App Mapping or reusable skills.

A failed or ambiguous action never becomes learned authority.

### 3.4 Re-ground, never blindly replay

Stored actions are templates, not absolute coordinates.

Before reuse, V5 must re-ground against current package, screen signature, semantic anchors, visual anchors, dimensions, orientation, and app version confidence.

### 3.5 Risk authority is external and monotonic

Memory, repetition, confidence, and previous success never lower a risk class or widen capability scope.

---

## 4. Top-level architecture

```text
ChatGPT / GitHub control
          |
          v
Cloudflare Task Gateway
          |
          | task goal / cancellation / checkpoint reasoning
          v
+--------------------------------------------------+
| Android Brain Agent V5                           |
|                                                  |
|  Unified Intent                                  |
|       |                                          |
|  UnifiedOperatorEngine                           |
|       |                                          |
|  +----+------------------------------+           |
|  | Unified Perception                |           |
|  | Dynamic Inference Budget          |           |
|  | Unified Planner                   |           |
|  | Unified Executor                  |           |
|  | Unified Verifier                  |           |
|  | Recovery Engine                   |           |
|  | Universal App Mapping Engine      |           |
|  | App / Domain Skill Adapters       |           |
|  +-----------------------------------+           |
|       |                                          |
| Accessibility / screenshots / Android APIs       |
+--------------------------------------------------+
```

GitHub Actions must remain outside the per-action loop. GitHub is dispatch/audit infrastructure, not a realtime game or interaction transport.

---

## 5. UnifiedObservation

Every iteration produces one logical `UnifiedObservation`. Not every field must be freshly captured every time.

Proposed schema:

```text
UnifiedObservation
- timestamp
- packageName
- appVersionHint
- activityHint
- windowId / windowTitle
- orientation
- screenWidth / screenHeight
- accessibilityRevision
- semanticNodes[]
- semanticFingerprint
- screenshotHash?
- perceptualHash?
- visualRegions[]?
- keyboardState?
- dialogState?
- foregroundConfidence
- screenSignature
- appMapMatch?
- skillSpecificState?
```

### 5.1 Event-driven perception

Accessibility events become the primary low-latency trigger when available:

- window changed;
- content changed;
- selection changed;
- text changed;
- focus changed;
- click/scroll feedback.

The engine should not poll continuously when an event can provide the same evidence.

### 5.2 Screenshot policy

Capture a screenshot when one or more are true:

- Accessibility tree is sparse or missing;
- foreground surface is Canvas/WebView/SurfaceView/custom renderer;
- semantic and expected state disagree;
- visual verification is required;
- a new screen needs visual mapping;
- a domain skill explicitly requires pixels;
- recovery requires an alternate perception channel.

Do not upload a screenshot to cloud merely because it was captured locally. Upload only the minimum necessary visual context when cloud reasoning is required.

### 5.3 Incremental observation reuse

V5 should cache the latest validated observation and update only changed channels when possible. This reduces repeated serialization, hashing, screenshot capture, and network transfer.

---

## 6. Dynamic Inference Budget

`DynamicInferenceBudget` decides how much reasoning is necessary for the current step while preserving a single engine abstraction.

Inputs include:

```text
confidence
knownScreenScore
knownTransitionScore
semanticCompleteness
visualAmbiguity
riskClass
reversibility
failureStreak
taskNovelty
plannerCost
```

Possible internal decisions are implementation details, not user-visible modes:

1. execute a verified local action immediately;
2. recompute local grounding;
3. run a local deterministic/domain solver;
4. obtain a new screenshot/visual feature set;
5. request a compact cloud micro-plan;
6. request deeper cloud recovery reasoning.

The task does not reset or change identity when escalation occurs.

---

## 7. Unified Planner

The planner consumes `UnifiedObservation`, `TaskIntent`, task memory, and matched App Map context.

It returns either:

```text
SingleAction
```

or a bounded:

```text
MicroPlan
- actions[2..8]
- preconditions[]
- perActionPostconditions[]
- abortConditions[]
- reobservePoints[]
- confidence
```

### 7.1 Micro-plan execution

A micro-plan may run locally without cloud round-trip after every step only when:

- each action is within existing capability scope;
- effective risk remains allowed;
- intermediate state has high-confidence expected transitions;
- actions are reversible or low consequence;
- verifier can detect divergence before the next consequential action.

Never speculative-batch Class C actions.

### 7.2 Predictive preparation

While a UI animation or gesture is completing, the engine may prepare likely next selectors, screen signatures, or candidate actions. It must not execute the next action until the required postcondition is verified.

---

## 8. Unified Executor

The executor remains typed and bounded. It must not expose raw shell, root commands, arbitrary scripts, or arbitrary code execution.

V5 reuses V4 typed actions and adds timing metadata where useful:

```text
ActionTiming
- gestureDurationMs
- minimumSettleMs
- maximumSettleMs
- eventDrivenCompletion
- retryPolicy
```

### 8.1 Adaptive gesture timing

A single hard-coded swipe duration is incorrect for all apps.

V5 learns an app/screen-specific safe timing envelope from verified executions.

Initial target ranges:

- simple tap dispatch: immediate once grounded;
- swipe gesture: approximately 60–120 ms when the target app reliably accepts it;
- slower fallback gesture: 120–220 ms when required by app behavior;
- post-action settle: event-driven where possible rather than fixed sleep.

These are technical targets, not guarantees. Android scheduling, OEM behavior, animation, frame rate, and app implementation can require longer timing.

### 8.2 Per-app latency profile

Verified measurements may update:

```text
LatencyProfile
- medianActionToEventMs
- p90ActionToEventMs
- reliableSwipeDurationMs
- reliableTapSettleMs
- screenshotCostMs
```

This profile improves scheduling but never changes risk authority.

---

## 9. Unified Verifier

Verification is multimodal and task-specific.

Evidence may include:

- package change;
- activity/window change;
- semantic fingerprint change;
- target node state change;
- screenshot/perceptual hash change;
- visual region change;
- task-specific state transition;
- score/tile/state change from a deterministic skill;
- expected screen signature match.

A successful action means the required postcondition is observed. Dispatch alone is never success.

### 9.1 Visual-only surfaces

For Canvas/WebView/game interfaces, unchanged Accessibility fingerprints do not imply `NO_OP`.

The verifier must use visual or domain-specific state before declaring failure.

### 9.2 Divergence detection

If a micro-plan expected `Screen B` after action 2 but observes an unrelated state, execution stops the micro-plan immediately and returns to the unified loop for re-grounding/recovery.

---

## 10. Universal App Understanding & Mapping Engine

Universal App Mapping is a first-class V5 subsystem.

Its contract is:

```text
Recognize -> Explore -> Map -> Verify -> Reuse -> Decay / Re-ground
```

### 10.1 AppProfile

```text
AppProfile
- packageName
- labels[]
- versionHints[]
- firstSeenAt
- lastSeenAt
- screenGraphVersion
- globalVisualAnchors[]
- globalSemanticAnchors[]
- latencyProfile
- explorationPolicy
- confidence
```

Package name remains the primary app identity. Label or icon alone is never sufficient.

### 10.2 ScreenGraph

A screen is a logical UI state, not merely an Android Activity.

```text
ScreenState
- screenId
- packageName
- activityHint?
- semanticSignature
- visualSignature?
- landmarkAnchors[]
- knownElements[]
- knownTransitions[]
- lastVerifiedAppVersion?
- confidence
- firstSeenAt
- lastVerifiedAt
```

The same Activity may contain multiple `ScreenState` nodes.

### 10.3 ElementGraph

```text
ElementDescriptor
- elementId
- semanticRole?
- resourceIds[]
- textAnchors[]
- contentDescriptionAnchors[]
- relativeBounds?
- visualAnchors[]?
- supportedActions[]
- confidence
- staleScore
```

Absolute coordinates may be stored only as weak evidence from a verified screen instance. They cannot be primary identity across changed layouts.

### 10.4 TransitionGraph

```text
TransitionEdge
- fromScreenId
- actionTemplate
- toScreenId
- preconditions[]
- postconditions[]
- semanticAnchors[]
- visualAnchors[]
- successCount
- failureCount
- medianLatencyMs
- lastVerifiedAt
- confidence
```

This lets V5 solve navigation as state-graph pathfinding when a verified path exists.

### 10.5 VerifiedSkills

A repeated successful trajectory may become a reusable app-scoped skill:

```text
VerifiedSkill
- skillId
- packageName / allowedPackages[]
- intentPattern
- entryScreenPatterns[]
- actionTemplates[]
- expectedTransitions[]
- capabilityScope
- riskCeiling
- appVersionHints[]
- successEvidence
- confidence
```

A skill remains subordinate to current observation and risk policy.

### 10.6 RecoveryPatterns

Recovery patterns store safe alternatives that succeeded in the past, for example:

- semantic selector missing -> visual anchor fallback;
- keyboard covers control -> dismiss keyboard -> re-ground;
- dialog appears -> handle known safe dialog;
- tab layout changed -> search by text/role;
- scroll target moved -> bounded search scroll.

---

## 11. Autonomous app exploration

V5 may safely explore an unfamiliar app to improve its map.

### 11.1 Allowed exploration

Without additional confirmation, exploration may use Class-A navigation such as:

- open menus;
- switch tabs;
- scroll;
- open non-destructive detail pages;
- Back;
- inspect Settings pages;
- close ordinary informational dialogs;
- observe controls without activating consequential actions.

### 11.2 Forbidden autonomous exploration

Exploration must not intentionally trigger:

- purchase/payment;
- send/post/publish;
- delete/uninstall;
- account mutation;
- permission widening beyond an explicitly approved flow;
- financial actions;
- credential/OTP/private-key flows;
- security bypass;
- biometric/CAPTCHA bypass.

### 11.3 Exploration stop conditions

Exploration pauses when:

- only unknown consequential actions remain;
- the app requests credentials or sensitive authentication;
- a secure surface prevents observation;
- repeated states indicate no useful new coverage;
- user leaves the allowed app scope.

---

## 12. Memory quality and confidence decay

V5 must not let old UI knowledge become permanent truth.

Confidence decays when:

- app version changes;
- semantic anchors disappear;
- visual signature diverges;
- a stored transition fails;
- a skill has not been verified for a long time;
- screen dimensions/orientation differ materially;
- repeated recovery is required.

High-confidence memory accelerates planning. Low-confidence memory becomes a hint only.

Memory promotion requires **verified success**. Failure evidence may reduce confidence but must not automatically invent a replacement mapping.

---

## 13. Local storage and privacy

App Mapping should be primarily stored on-device because it reflects private app structure and usage.

Recommended storage split:

### On device

- AppProfile;
- ScreenGraph;
- ElementGraph;
- TransitionGraph;
- latency profiles;
- verified skill templates;
- recovery patterns;
- confidence metadata.

### Cloud task state

Only sanitized data required for cross-session control/recovery:

- task ID;
- allowed package scope;
- progress/checkpoint metadata;
- compact screen identifiers/signatures where safe;
- selected skill ID;
- action/result metadata;
- sanitized error codes.

Do not persist raw screenshots, raw private UI trees, credentials, OTPs, passwords, private keys, or hidden chain-of-thought as durable cloud memory.

---

## 14. Persistent Operator Sessions

V5 introduces explicit session lifetime semantics.

```text
OperatorSession
- taskId
- goal
- allowedPackages[]
- primaryTargetPackage?
- persistencePolicy
- completionCriteria[]
- stopConditions[]
- currentCheckpoint
- userCancelled
```

### 14.1 Persistence policies

- `UNTIL_GOAL_COMPLETE`: ordinary task ends when verified completion criteria are satisfied.
- `UNTIL_USER_STOP`: task intentionally has no ordinary action-count terminal condition.
- `UNTIL_APP_SCOPE_EXIT`: continue while foreground state remains inside the allowed app scope.

These policies can be combined where the goal requires it.

### 14.2 “Only stop when I say stop or exit the app”

For a single-app persistent task, the intended semantics are:

```text
continue indefinitely
while:
  userCancelled == false
  AND foregroundPackage is within allowedPackages
  AND no hard safety block exists
```

If the user intentionally leaves the target app, V5 terminates that session rather than following them into unrelated apps.

For legitimate cross-app workflows, `allowedPackages` contains all explicitly required packages, so switching between those packages is not interpreted as user exit.

### 14.3 Step budgets become checkpoint controls

Long-running `UNTIL_USER_STOP` sessions are not considered failed merely because they exceeded 900 or 1000 actions.

They must still use bounded rolling budgets for:

- checkpoint cadence;
- repeated-state detection;
- resource control;
- recovery limits per unresolved state;
- watchdogs;
- cancellation responsiveness.

---

## 15. Stop and cancellation semantics

User cancellation is a first-class control path.

Required behavior:

1. user says “dừng”, “stop”, or equivalent;
2. control bridge resolves the active task/session;
3. gateway marks cancellation intent;
4. persistent WebSocket pushes cancellation to device;
5. local engine aborts before the next non-atomic action;
6. device posts `CANCELLED` receipt;
7. task state remains auditable without raw private screen content.

Cancellation must not depend on waiting for a long cloud-planner timeout.

The local kill switch remains authoritative and immediate.

---

## 16. Recovery engine

Recovery is part of ordinary execution, not an afterthought.

Suggested escalation sequence:

```text
1. re-observe changed semantic state
2. re-ground known element
3. try verified alternate semantic selector
4. obtain visual observation
5. try verified visual recovery pattern
6. search nearby screen graph transitions
7. request cloud recovery reasoning
8. fail/pause only when safe recovery is exhausted
```

A recovery budget is scoped to an unresolved state, not the entire long-running session.

Repeated failure in one state must not poison unrelated later states.

---

## 17. Domain skills inside the unified engine

Domain/game skills remain plugins to the same engine. They are not separate operating modes.

A skill may provide:

- state extractor;
- local solver;
- legal action generator;
- task-specific verifier;
- recovery hints;
- terminal-state detector.

The engine still owns:

- permissions;
- package scope;
- cancellation;
- task lifetime;
- risk clamp;
- memory admission;
- observability.

---

## 18. 2048 as a reference workload

2048 is used as an acceptance workload for low-latency visual/deterministic operation, not as a special architecture.

Target flow:

```text
observe board locally
 -> parse 4x4 state
 -> local solver selects move
 -> fast adaptive swipe
 -> verify board state
 -> repeat
```

No cloud round-trip is required per move once the board is reliably grounded.

When `Game Over` is detected:

```text
terminal state
 -> locate Try Again / New Game
 -> confirm new board state
 -> resume solver loop
```

For a task such as “play until I tell you to stop”:

- Game Over does not complete the task;
- restart is automatic when safe and inside the game;
- session continues indefinitely through repeated games;
- user cancellation stops it;
- intentional foreground exit from the target app stops it;
- ads, purchases, external links, account controls, and unrelated UI remain forbidden.

---

## 19. Latency targets

Targets apply to the local execution path where Android/app behavior permits them.

```text
Known local action decision:        target < 30-80 ms
Local verification:                 target ~20-100 ms
Fast accepted swipe duration:       target ~60-120 ms
Fallback swipe duration:            up to ~220 ms when required
Cloud calls for familiar sequences: avoid per step
Micro-plan length:                  default 2-8 actions
```

Latency optimization must never skip required postcondition checks before consequential actions.

Performance telemetry should record bounded operational measurements such as action-to-event latency and verifier latency, never hidden reasoning or sensitive content.

---

## 20. Gateway and protocol changes

The V5 gateway contract should support the unified device loop rather than micromanage every action.

Required capabilities:

- task creation with `persistencePolicy` and `allowedPackages`;
- cancel active task/session;
- checkpoint upload;
- optional cloud micro-plan request;
- optional recovery reasoning request;
- task status query;
- device receipts;
- task-bound confirmation for Class C;
- WebSocket push for task start/cancel/reasoning response.

A V5 task should be able to remain locally active while the cloud is temporarily unavailable, provided:

- all pending actions are already authorized;
- the task remains within allowed package scope;
- local confidence remains adequate;
- no cloud-only reasoning is required;
- no safety confirmation is pending.

If these conditions cease to hold, the local engine pauses rather than guessing.

---

## 21. Android implementation components

Expected component boundaries:

```text
agent/
  UnifiedOperatorEngine.kt
  DynamicInferenceBudget.kt
  MicroPlan.kt
  PersistentOperatorSession.kt

perception/
  UnifiedObservation.kt
  ObservationCache.kt
  EventDrivenObserver.kt
  VisualStateProvider.kt

mapping/
  AppProfile.kt
  ScreenGraph.kt
  ElementGraph.kt
  TransitionGraph.kt
  AppMappingStore.kt
  AppExplorer.kt
  ConfidenceDecay.kt

execution/
  AdaptiveActionScheduler.kt
  ActionTimingProfile.kt

verification/
  UnifiedVerifier.kt
  VisualVerifier.kt
  SemanticVerifier.kt

recovery/
  RecoveryEngine.kt

skills/
  existing app/domain/game skills
```

The exact file split may adapt to current code conventions, but component responsibilities must remain isolated and testable.

---

## 22. Compatibility and migration from V4

V5 must preserve:

- existing pairing identity and device trust where signer continuity permits;
- task-first `/run` bridge;
- typed action schema compatibility;
- V4 risk classes A/B/C/D;
- task-bound Class-C confirmation;
- reverse WebSocket architecture;
- kill switch;
- screenshot redaction and secure-window behavior;
- V4 AppSkillMemory data where it can be safely migrated.

V4 app-skill records should be imported as low/medium-confidence candidates, then re-verified before becoming high-confidence V5 graph edges.

No migration may convert an old coordinate macro into trusted unconditional execution.

---

## 23. Safety boundary

V5 performance work must not weaken safety.

### Class A

Observe, navigate, scroll, open, Back/Home, safe non-mutating controls.

### Class B

Typing, reversible toggles, reversible edits under granted scope.

### Class C

Send, post, delete, uninstall, purchase, irreversible/external mutation. Requires exact task-bound explicit confirmation where policy requires it.

### Class D

Credential/OTP/private key/seed phrase extraction or unattended use, security bypass, financial transfer/signing, prohibited privilege escalation. Denied.

Additional rules:

- no speculative Class-C execution;
- no learned permission expansion;
- no CAPTCHA/biometric bypass;
- no `FLAG_SECURE` circumvention;
- no arbitrary shell/root/script execution;
- no hidden ADB control exposed to planner;
- no silent following of the user into unrelated apps during single-app persistent sessions.

---

## 24. Observability states

Device-operation reporting must continue to distinguish:

- `QUEUED`: gateway accepted the task/action;
- `DEVICE_EXECUTED`: device returned an execution receipt;
- `VERIFIED`: required postcondition or final success evidence was observed.

Never report `VERIFIED` from queue acceptance alone.

V5 should add operational metrics such as:

- localDecisionLatencyMs;
- actionDispatchLatencyMs;
- actionToEventLatencyMs;
- verifierLatencyMs;
- localVsCloudReasoningCount;
- screenMapHitRate;
- verifiedSkillHitRate;
- recoveryRate;
- screenshotRate;
- cancellationLatencyMs.

These metrics must not contain raw private screenshots, hidden chain-of-thought, credentials, or private message bodies.

---

## 25. Acceptance test matrix

V5 is not complete merely because unit tests or CI pass. A physical-device acceptance run is required.

### 25.1 Standard semantic app

- identify package correctly;
- recognize at least three distinct screens;
- navigate through a verified screen path;
- reuse learned path with fewer cloud calls;
- recover from one moved/missing control.

### 25.2 Deep menu/settings app

- navigate >10 actions;
- use screen graph transitions;
- verify final state;
- checkpoint and resume.

### 25.3 WebView/browser UI

- detect sparse semantic tree;
- invoke visual support;
- act and verify without false `NO_OP`.

### 25.4 Canvas/game workload

2048 must demonstrate:

- local board/state perception;
- local solver loop;
- adaptive fast swipes;
- >100 consecutive actions;
- no per-move cloud dependency;
- Game Over recognition;
- automatic restart;
- repeated play after restart;
- user cancellation;
- stop on intentional target-app exit.

### 25.5 Persistent >1000-action workload

- rolling checkpoints continue;
- no ordinary `STEP_LIMIT` termination;
- repeated-state/recovery budgets remain bounded;
- cancellation still responds promptly.

### 25.6 App mapping

On an unfamiliar safe test app:

- create AppProfile;
- discover multiple ScreenState nodes;
- record verified TransitionEdges;
- reuse a transition successfully;
- invalidate or reduce confidence when UI changes.

### 25.7 Network degradation

During an active locally solvable task:

- disconnect cloud temporarily;
- continue only while local authorization/confidence are sufficient;
- pause safely if cloud reasoning becomes necessary;
- reconnect without corrupting task identity.

### 25.8 Safety regression

Verify that V5 still blocks or confirms as required for:

- delete;
- purchase;
- send/post;
- credentials/OTP/private keys;
- secure-window restrictions;
- unrelated app escape from a single-app session.

---

## 26. Test strategy

Implementation must follow repository engineering policy:

```text
RED
 -> minimum GREEN
 -> regression suite
 -> Android lint/build
 -> gateway tests
 -> CI
 -> merge
 -> exact-main deployment verification
 -> physical-device acceptance
```

Required test categories:

- `DynamicInferenceBudget` decision tests;
- `UnifiedObservation` cache/invalidation tests;
- micro-plan abort/reobserve tests;
- adaptive gesture timing tests;
- package/screen identity tests;
- ScreenGraph / TransitionGraph persistence tests;
- confidence-decay tests;
- safe exploration tests;
- memory admission only after verified success;
- visual-only verifier regression;
- persistent-session no-step-limit regression;
- cancellation semantics;
- app-scope exit semantics;
- 2048 restart/continuous-loop tests;
- V4 compatibility/migration tests;
- risk non-regression tests.

---

## 27. Rollout strategy

V5 rollout should be incremental even though the runtime abstraction is unified.

### Phase 1 — unified observation/verifier foundation

- add `UnifiedObservation`;
- cache/event-driven updates;
- multimodal verifier;
- preserve V4 behavior behind compatibility adapters.

### Phase 2 — unified local operator loop

- add `UnifiedOperatorEngine`;
- dynamic inference budget;
- micro-plan local execution;
- adaptive action scheduler;
- cloud escalation contract.

### Phase 3 — Universal App Mapping

- AppProfile / ScreenGraph / ElementGraph / TransitionGraph;
- verified learning;
- confidence decay;
- safe exploration;
- path reuse.

### Phase 4 — persistent sessions

- `UNTIL_USER_STOP`;
- app-scope exit semantics;
- rolling checkpoints without ordinary step-limit failure;
- fast cancellation.

### Phase 5 — physical-device acceptance and optimization

- standard apps;
- WebView;
- Canvas/game;
- 2048 continuous restart;
- >1000-action run;
- latency tuning;
- app-map reuse benchmark.

No phase may weaken V4 safety boundaries to gain speed.

---

## 28. Success criteria

V5 is considered successful when all of the following are true:

1. There is one user-visible operator model, not separate A/B/Fast/Smart modes.
2. Familiar low-risk actions can execute locally without a cloud round-trip per step.
3. Complex states can automatically obtain deeper/cloud reasoning without task reset.
4. Screenshot use is selective and driven by need.
5. App identity uses package-level grounding and screen identity uses composite semantic/visual state.
6. The system builds and reuses verified per-app Screen/Element/Transition graphs.
7. Learned knowledge always re-grounds before action and decays when stale.
8. Persistent `UNTIL_USER_STOP` tasks do not terminate because of arbitrary action-count limits.
9. User cancellation and app-scope exit stop persistent tasks correctly.
10. 2048 can run locally, restart after Game Over, and continue until stop/exit.
11. Cloud outage cannot silently cause unsafe guessing.
12. Risk classes and Class-C confirmation remain at least as strict as V4.
13. Physical-device evidence proves semantic, WebView, Canvas/game, long-running, recovery, mapping, cancellation, and safety behavior.
14. Completion reporting distinguishes `QUEUED`, `DEVICE_EXECUTED`, and `VERIFIED`.

---

## 29. Explicit non-goals

V5 does not promise reliable automation of every possible Android surface.

Out of scope or fail-closed includes:

- CAPTCHA solving/bypass;
- biometric/lock-screen bypass;
- secure-window circumvention;
- root/privilege escalation;
- arbitrary shell or script execution;
- unattended credential/OTP/private-key use;
- high-frequency realtime game control requiring frame-perfect 30–60 FPS unless a future explicitly approved local deterministic adapter can safely support it;
- silently operating outside the user-authorized package/capability scope.

---

## 30. Final architectural decision

Unified Adaptive Android Brain V5 is defined by this invariant:

> **One continuous operator loop automatically balances speed, perception depth, reasoning depth, local execution, cloud assistance, verification, recovery, and app memory without exposing separate execution modes to the user.**

Universal App Mapping is part of that loop, not an optional side system. Every successful verified interaction may improve future app understanding, while every reused action remains re-grounded and subordinate to current UI evidence and safety policy.

This design supersedes V4 only for the execution/mapping architecture described here. V4 security, typed-action, task-bound confirmation, device trust, WebSocket, and observability guarantees remain inherited unless this spec explicitly strengthens them.
