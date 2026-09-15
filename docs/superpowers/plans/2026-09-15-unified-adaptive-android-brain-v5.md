# Unified Adaptive Android Brain V5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Android Brain Agent V5 as one low-latency adaptive operator that executes familiar safe actions locally, escalates reasoning only when necessary, learns verified per-app structure, and supports persistent sessions that stop only on user-defined stop conditions.

**Architecture:** Keep V4 pairing, typed actions, task-first `/run`, reverse WebSocket, risk classes, kill switch, and Cloudflare task state. Add a device-side `UnifiedOperatorEngine` that owns event-driven observation, adaptive inference, micro-plan execution, multimodal verification, app mapping, recovery, and persistent-session semantics. Cloud reasoning is an extension of the same task state and is requested only when local grounding is insufficient; GitHub remains dispatch/audit only and never enters the per-action loop.

**Tech Stack:** Kotlin/JVM 17, Android SDK 35 / minSdk 26, Android AccessibilityService, OkHttp 4.12 WebSocket/HTTP, kotlinx-coroutines 1.9, JUnit 4, Node.js 24, Cloudflare Workers, Wrangler 4.124.0, Node built-in test runner.

**Spec:** `docs/superpowers/specs/2026-09-15-unified-adaptive-android-brain-v5-design.md`

## Global Constraints

- One user-visible operator only; do not expose A/B/Fast/Smart/game/cloud modes.
- Preserve applicationId `com.hanlinh.androidbrain`; target V5 release `0.5.0`, proposed versionCode `14`.
- Preserve V4 pairing/device trust, typed action compatibility, task-first `/run`, reverse WebSocket, kill switch, screenshot redaction, secure-window behavior, and A/B/C/D risk semantics.
- Class C remains exact task-bound confirmation; Class D remains denied.
- No raw shell, root, hidden ADB, arbitrary script engine, CAPTCHA/biometric bypass, `FLAG_SECURE` circumvention, credential/OTP/private-key unattended handling, or learned permission expansion.
- Familiar local actions may avoid cloud round-trips only when current grounding, capability scope, risk, and verification permit it.
- Learned app knowledge is app-scoped, re-grounded before reuse, and admitted only after verified success.
- `UNTIL_USER_STOP` sessions must not fail from ordinary action-count limits; bounded checkpoints/recovery/watchdogs still apply.
- Physical-device evidence is required before V5 can be called `VERIFIED`; CI success alone is insufficient.
- Device-operation reporting must keep `QUEUED`, `DEVICE_EXECUTED`, and `VERIFIED` distinct.
- Engineering sequence is mandatory: RED -> minimum GREEN -> regression suite -> Android lint/build -> gateway tests -> CI -> merge -> exact-main deployment verification -> physical-device acceptance.

---

## File Structure Lock

Create focused Android components instead of growing `AgentConnectionManager.kt` or `CommandDispatcher.kt` into new monoliths:

```text
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/
  agent/
    DynamicInferenceBudget.kt
    MicroPlan.kt
    PersistentOperatorSession.kt
    UnifiedOperatorEngine.kt
  perception/
    EventDrivenObserver.kt
    ObservationCache.kt
    UnifiedObservation.kt
    VisualStateProvider.kt
  verification/
    SemanticVerifier.kt
    UnifiedVerifier.kt
    VisualVerifier.kt
  mapping/
    AppExplorer.kt
    AppMappingStore.kt
    AppProfile.kt
    ConfidenceDecay.kt
    ElementGraph.kt
    ScreenGraph.kt
    TransitionGraph.kt
  execution/
    ActionTimingProfile.kt
    AdaptiveActionScheduler.kt
  recovery/
    RecoveryEngine.kt
```

Existing integration points expected to change:

```text
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/BrainAccessibilityService.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskProgress.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskSessionEngine.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Session.kt
android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Solver.kt
android-brain-agent/app/build.gradle.kts

android-agent-gateway/src/task-intent.js
android-agent-gateway/src/device-session.js
android-agent-gateway/src/index.js
android-agent-gateway/src/planner.js
android-agent-gateway/src/app-skill-memory.js
.github/workflows/android-brain-agent-ci.yml
.github/workflows/android-brain-agent-command-v4.yml
```

---

### Task 1: Define V5 Session and Observation Contracts

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/PersistentOperatorSession.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/UnifiedObservation.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskProgress.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/PersistentOperatorSessionTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/UnifiedObservationTest.kt`

**Interfaces:**
- Consumes: existing `RiskClass`, V4 task ID, package identity, `AccessibilitySnapshot` fields.
- Produces: `PersistencePolicy`, `PersistentOperatorSession`, and `UnifiedObservation` used by all later V5 components.

- [ ] **Step 1: Write failing persistent-session tests**

```kotlin
@Test fun untilUserStop_doesNotExpireFromStepCount() {
    val session = PersistentOperatorSession(
        taskId = "t1",
        goal = "play until I stop",
        allowedPackages = setOf("com.example.game"),
        persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
    )
    assertFalse(session.shouldStop("com.example.game", userCancelled = false, hardSafetyBlock = false))
}

@Test fun appScopeExit_stopsSingleAppSession() {
    val session = PersistentOperatorSession(
        taskId = "t1",
        goal = "play until I stop",
        allowedPackages = setOf("com.example.game"),
        persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
    )
    assertTrue(session.shouldStop("com.android.launcher", userCancelled = false, hardSafetyBlock = false))
}
```

- [ ] **Step 2: Write failing observation identity tests**

```kotlin
@Test fun screenSignature_changesWhenSemanticStateChanges() {
    val a = UnifiedObservation.signature("com.example", "screenA", "sem-a", null, 1080, 2400, "PORTRAIT")
    val b = UnifiedObservation.signature("com.example", "screenA", "sem-b", null, 1080, 2400, "PORTRAIT")
    assertNotEquals(a, b)
}
```

- [ ] **Step 3: Run focused tests and verify RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*PersistentOperatorSessionTest' --tests '*UnifiedObservationTest' --stacktrace
```

Expected: FAIL because V5 contract types do not exist.

- [ ] **Step 4: Implement minimal contracts**

```kotlin
enum class PersistencePolicy {
    UNTIL_GOAL_COMPLETE,
    UNTIL_USER_STOP,
    UNTIL_APP_SCOPE_EXIT,
}

data class PersistentOperatorSession(
    val taskId: String,
    val goal: String,
    val allowedPackages: Set<String>,
    val persistence: Set<PersistencePolicy>,
) {
    fun shouldStop(foregroundPackage: String, userCancelled: Boolean, hardSafetyBlock: Boolean): Boolean {
        if (userCancelled || hardSafetyBlock) return true
        return PersistencePolicy.UNTIL_APP_SCOPE_EXIT in persistence && foregroundPackage !in allowedPackages
    }
}
```

`UnifiedObservation` must carry timestamp, package, app-version hint, activity hint, window title, orientation, dimensions, semantic fingerprint, optional screenshot/perceptual hash, semantic node count, and screen signature. Provide a deterministic `signature(...)` helper using SHA-256 over normalized non-sensitive metadata.

- [ ] **Step 5: Add V4 compatibility mapping**

Keep existing `TaskPersistence.ONE_SHOT`, `LONG_RUNNING`, and `UNTIL_TERMINAL` serialized behavior intact. Add a conversion function from V4 persistence into V5 policy rather than renaming/removing enum members.

- [ ] **Step 6: Run focused tests to GREEN**

```bash
gradle testDebugUnitTest --tests '*PersistentOperatorSessionTest' --tests '*UnifiedObservationTest' --stacktrace
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/PersistentOperatorSession.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/UnifiedObservation.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskProgress.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/PersistentOperatorSessionTest.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/UnifiedObservationTest.kt
git commit -m "feat(android-v5): define unified session and observation contracts"
```

---

### Task 2: Add Event-Driven Observation Cache

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/ObservationCache.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/EventDrivenObserver.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/VisualStateProvider.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/BrainAccessibilityService.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/ObservationCacheV5Test.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception/EventDrivenObserverTest.kt`

**Interfaces:**
- Consumes: `AccessibilitySnapshot`, `AccessibilityEvent.eventType`, screenshot capture callback.
- Produces: `EventDrivenObserver.latest(): UnifiedObservation?`, semantic revision tracking, and selective visual-capture requests.

- [ ] **Step 1: Write failing cache invalidation tests**

```kotlin
@Test fun contentChange_invalidatesSemanticRevisionWithoutForcingScreenshot() {
    val cache = ObservationCache()
    cache.updateSemantic(snapshot("com.example", nodeCount = 20))
    val before = cache.semanticRevision
    cache.markAccessibilityChanged(AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED)
    assertTrue(cache.semanticRevision > before)
    assertFalse(cache.visualCaptureRequired)
}

@Test fun sparseTree_requestsVisualState() {
    val cache = ObservationCache()
    cache.updateSemantic(snapshot("com.example", nodeCount = 1))
    assertTrue(cache.shouldCaptureVisual())
}
```

- [ ] **Step 2: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*ObservationCacheV5Test' --tests '*EventDrivenObserverTest' --stacktrace
```

Expected: FAIL because cache/observer types do not exist.

- [ ] **Step 3: Implement event forwarding in `BrainAccessibilityService`**

```kotlin
override fun onAccessibilityEvent(event: AccessibilityEvent?) {
    if (event == null) return
    EventDrivenObserver.current?.onAccessibilityEvent(event.eventType)
}
```

`EventDrivenObserver` must debounce duplicate event bursts but preserve distinct window/content/focus/scroll/text revisions.

- [ ] **Step 4: Implement selective screenshot policy**

`ObservationCache.shouldCaptureVisual()` returns true only when semantic state is sparse, an explicit visual verifier/domain skill requests pixels, a new screen has no visual signature, or semantic/postcondition evidence conflicts. A normal accessibility update does not automatically trigger a screenshot.

- [ ] **Step 5: Run focused and existing snapshot tests**

```bash
gradle testDebugUnitTest --tests '*ObservationCacheV5Test' --tests '*EventDrivenObserverTest' --tests '*AccessibilitySnapshot*' --stacktrace
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/service/BrainAccessibilityService.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/perception
git commit -m "feat(android-v5): add event-driven unified perception"
```

---

### Task 3: Build Multimodal Unified Verification

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/verification/SemanticVerifier.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/verification/VisualVerifier.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/verification/UnifiedVerifier.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/Verifier.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/verification/UnifiedVerifierTest.kt`

**Interfaces:**
- Consumes: before/after `UnifiedObservation`, expected package/screen signature, optional skill-specific state token.
- Produces: `VerificationResult(success, changed, confidence, reason)`.

- [ ] **Step 1: Write failing visual-only regression tests**

```kotlin
@Test fun unchangedAccessibility_butChangedVisual_isProgress() {
    val before = observation(semantic = "same", visual = "aaa")
    val after = observation(semantic = "same", visual = "bbb")
    val result = UnifiedVerifier().verifyTransition(before, after)
    assertTrue(result.changed)
    assertTrue(result.success)
}

@Test fun unchangedSemanticAndVisual_isNoOp() {
    val before = observation(semantic = "same", visual = "aaa")
    val result = UnifiedVerifier().verifyTransition(before, before)
    assertFalse(result.changed)
}
```

- [ ] **Step 2: Run tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*UnifiedVerifierTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 3: Implement verification result contract**

```kotlin
data class VerificationResult(
    val success: Boolean,
    val changed: Boolean,
    val confidence: Double,
    val reason: String,
)
```

Package/postcondition evidence outranks generic fingerprint change. A fresh visual/domain change can prove progress even when accessibility is unchanged. Semantic equality alone must not emit `NO_OP` when visual/domain evidence shows progress.

- [ ] **Step 4: Adapt legacy `Verifier` to delegate to V5 when a `UnifiedObservation` is present**

Keep legacy behavior for V4 call sites until Task 8 removes the old per-step assumption.

- [ ] **Step 5: Run verifier and V4 session regression tests**

```bash
gradle testDebugUnitTest --tests '*UnifiedVerifierTest' --tests '*VerifierTest' --tests '*TaskSessionEngine*' --stacktrace
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/verification \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/Verifier.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/verification
git commit -m "feat(android-v5): add multimodal verification"
```

---

### Task 4: Implement Dynamic Inference Budget and Micro-Plans

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/DynamicInferenceBudget.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/MicroPlan.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/DynamicInferenceBudgetTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/MicroPlanTest.kt`

**Interfaces:**
- Consumes: confidence, known-screen score, known-transition score, semantic completeness, visual ambiguity, risk, reversibility, failure streak, task novelty.
- Produces: `InferenceDirective` and bounded `MicroPlan` containing typed actions and re-observation points.

- [ ] **Step 1: Write failing inference tests**

```kotlin
@Test fun familiarLowRiskState_executesLocally() {
    val directive = DynamicInferenceBudget().decide(
        InferenceSignals(
            confidence = 0.97,
            knownScreen = 0.95,
            knownTransition = 0.94,
            semanticCompleteness = 0.95,
            visualAmbiguity = 0.05,
            riskClass = RiskClass.A,
            reversible = true,
            failureStreak = 0,
            taskNovelty = 0.05,
        )
    )
    assertEquals(InferenceDirective.LOCAL_EXECUTE, directive)
}
```

- [ ] **Step 2: Write failing Class-C speculation guard test**

```kotlin
@Test fun classC_neverSpeculates() {
    val plan = MicroPlan(actions = listOf(classCAction()), reobserveAfter = emptySet(), confidence = 0.99)
    assertFalse(plan.isEligibleForSpeculativeExecution())
}
```

- [ ] **Step 3: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*DynamicInferenceBudgetTest' --tests '*MicroPlanTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement inference directives and bounded micro-plan**

```kotlin
enum class InferenceDirective {
    LOCAL_EXECUTE,
    LOCAL_REGROUND,
    LOCAL_DOMAIN_SOLVER,
    CAPTURE_VISUAL,
    CLOUD_MICRO_PLAN,
    CLOUD_RECOVERY,
}

data class MicroPlan(
    val actions: List<Action>,
    val reobserveAfter: Set<Int>,
    val confidence: Double,
) {
    init { require(actions.size in 1..8) }
    fun isEligibleForSpeculativeExecution(): Boolean = actions.none { it.riskClass.ordinal >= RiskClass.C.ordinal }
}
```

- [ ] **Step 5: Run focused and risk-policy regression tests**

```bash
gradle testDebugUnitTest --tests '*DynamicInferenceBudgetTest' --tests '*MicroPlanTest' --tests '*RiskPolicyTest' --stacktrace
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/DynamicInferenceBudget.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/MicroPlan.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/DynamicInferenceBudgetTest.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/MicroPlanTest.kt
git commit -m "feat(android-v5): add adaptive inference and micro-plans"
```

---

### Task 5: Implement Universal App Mapping and Confidence Decay

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/AppProfile.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/ScreenGraph.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/ElementGraph.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/TransitionGraph.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/AppMappingStore.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/ConfidenceDecay.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/AppMappingStoreTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/ConfidenceDecayTest.kt`

**Interfaces:**
- Consumes: verified `UnifiedObservation`, verified action transition, package/app-version hints.
- Produces: app-scoped graph lookup, verified transition admission, and stale-confidence decay.

- [ ] **Step 1: Write failing verified-admission test**

```kotlin
@Test fun failedTransition_isNeverPromoted() {
    val store = InMemoryAppMappingStore()
    store.recordTransition(candidateTransition(), verified = false)
    assertTrue(store.transitions("com.example").isEmpty())
}
```

- [ ] **Step 2: Write failing confidence-decay test**

```kotlin
@Test fun versionChange_reducesConfidence() {
    val decay = ConfidenceDecay()
    assertTrue(decay.apply(0.95, versionChanged = true, anchorMismatch = false, ageDays = 1) < 0.95)
}
```

- [ ] **Step 3: Run mapping tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*AppMappingStoreTest' --tests '*ConfidenceDecayTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement graph records**

```kotlin
data class TransitionEdge(
    val fromScreenId: String,
    val actionKey: String,
    val toScreenId: String,
    val successCount: Int,
    val failureCount: Int,
    val medianLatencyMs: Long,
    val confidence: Double,
    val lastVerifiedAtMs: Long,
)
```

`AppProfile` is keyed primarily by package name; app label/icon may only be secondary metadata. Screen identity combines semantic signature and optional visual signature. Absolute coordinates may be retained only as weak evidence tied to one verified screen instance.

- [ ] **Step 5: Implement on-device persistence without adding a database dependency**

Use `SharedPreferences` JSON for V5.0.0. Key by package name, cap retained screens/transitions per app, and prune lowest-confidence stale records. Do not persist raw screenshots or private UI text bodies.

- [ ] **Step 6: Run mapping and serialization round-trip tests**

```bash
gradle testDebugUnitTest --tests '*mapping*' --stacktrace
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping
git commit -m "feat(android-v5): add universal app mapping"
```

---

### Task 6: Add Safe App Exploration, Graph Pathfinding, and Recovery

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/AppExplorer.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/recovery/RecoveryEngine.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/AppExplorerTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/recovery/RecoveryEngineTest.kt`

**Interfaces:**
- Consumes: current observation, app graph, typed action, risk class, failure context.
- Produces: safe exploration action, shortest verified graph path, ordered recovery directive.

- [ ] **Step 1: Write failing exploration safety tests**

```kotlin
@Test fun exploration_allowsSafeNavigationOnly() {
    val explorer = AppExplorer()
    assertTrue(explorer.mayExplore(globalBackAction()))
    assertFalse(explorer.mayExplore(deleteAction()))
    assertFalse(explorer.mayExplore(purchaseAction()))
}
```

- [ ] **Step 2: Write failing recovery-order test**

```kotlin
@Test fun recovery_prefersVerifiedSelectorBeforeCloud() {
    val result = RecoveryEngine().next(RecoveryContext(hasVerifiedAlternateSelector = true))
    assertEquals(RecoveryDirective.USE_VERIFIED_SELECTOR, result)
}
```

- [ ] **Step 3: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*AppExplorerTest' --tests '*RecoveryEngineTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement exact recovery order**

```text
REOBSERVE
REGROUND
USE_VERIFIED_SELECTOR
CAPTURE_VISUAL
USE_VERIFIED_VISUAL_RECOVERY
USE_GRAPH_PATH
REQUEST_CLOUD_RECOVERY
PAUSE_OR_FAIL
```

Recovery budget is scoped to the unresolved state, not the lifetime of a long-running session.

- [ ] **Step 5: Implement exploration stop conditions**

Exploration may emit only Class-A navigation. Stop on credentials/authentication, secure surface, app-scope exit, repeated no-new-coverage state, or unknown consequential-only controls.

- [ ] **Step 6: Run focused and risk regression tests**

```bash
gradle testDebugUnitTest --tests '*AppExplorerTest' --tests '*RecoveryEngineTest' --tests '*RiskPolicyTest' --stacktrace
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/AppExplorer.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/recovery/RecoveryEngine.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/AppExplorerTest.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/recovery/RecoveryEngineTest.kt
git commit -m "feat(android-v5): add safe exploration and recovery"
```

---

### Task 7: Add Adaptive Action Scheduling and Per-App Timing Profiles

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/execution/ActionTimingProfile.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/execution/AdaptiveActionScheduler.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/execution/AdaptiveActionSchedulerTest.kt`

**Interfaces:**
- Consumes: package/screen identity, prior verified latency, typed action.
- Produces: `ActionTiming` and updated latency profile.

- [ ] **Step 1: Write failing fast-swipe test**

```kotlin
@Test fun knownFastScreen_usesFastSwipeEnvelope() {
    val scheduler = AdaptiveActionScheduler()
    val timing = scheduler.timingFor("com.example", "screenA", swipeAction(), profile(medianMs = 70))
    assertTrue(timing.gestureDurationMs in 60L..120L)
}
```

- [ ] **Step 2: Write failing backoff test**

```kotlin
@Test fun repeatedMisses_backOffGestureDuration() {
    val scheduler = AdaptiveActionScheduler()
    val first = scheduler.timingFor("com.example", "screenA", swipeAction(), profile(medianMs = 70))
    val retry = scheduler.afterFailedDispatch(first)
    assertTrue(retry.gestureDurationMs > first.gestureDurationMs)
    assertTrue(retry.gestureDurationMs <= 220L)
}
```

- [ ] **Step 3: Run test to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*AdaptiveActionSchedulerTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement timing profile and scheduler**

```kotlin
data class ActionTiming(
    val gestureDurationMs: Long,
    val minimumSettleMs: Long,
    val maximumSettleMs: Long,
    val eventDrivenCompletion: Boolean,
)
```

Initial fast swipe envelope is 60–120 ms. Backoff may rise to 220 ms. Event-driven verification ends settling earlier when the required UI event arrives.

- [ ] **Step 5: Thread adaptive duration through gesture execution**

`AccessibilityActions` must use the action/scheduler supplied gesture duration instead of imposing a universal 220 ms default where a typed `Swipe.durationMs` is present.

- [ ] **Step 6: Run focused and action regression tests**

```bash
gradle testDebugUnitTest --tests '*AdaptiveActionSchedulerTest' --tests '*TypedAction*' --stacktrace
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/execution \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/execution
git commit -m "feat(android-v5): add adaptive action scheduling"
```

---

### Task 8: Implement the Unified Local Operator Loop

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/UnifiedOperatorEngine.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskSessionEngine.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/UnifiedOperatorEngineTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/PersistentLoopV5Test.kt`

**Interfaces:**
- Consumes: `PersistentOperatorSession`, `EventDrivenObserver`, `DynamicInferenceBudget`, `UnifiedVerifier`, `AppMappingStore`, `AdaptiveActionScheduler`, `RecoveryEngine`, existing dispatcher.
- Produces: local continuous task progression, cloud escalation request only when required, and sanitized checkpoint/result metadata.

- [ ] **Step 1: Write failing local-loop test**

```kotlin
@Test fun familiarVerifiedPath_executesMultipleLocalStepsWithoutCloudPerStep() {
    val engine = testEngine(knownTransitions = 3)
    val result = engine.runUntilEscalation(maxLocalActions = 3)
    assertEquals(3, result.executedLocalActions)
    assertEquals(0, result.cloudRequests)
}
```

- [ ] **Step 2: Write failing persistent-step-limit regression**

```kotlin
@Test fun untilUserStop_survivesMoreThanOneThousandActions() {
    val engine = persistentTestEngine()
    repeat(1_050) { engine.recordVerifiedLocalAction() }
    assertFalse(engine.currentSession().terminal)
}
```

- [ ] **Step 3: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*UnifiedOperatorEngineTest' --tests '*PersistentLoopV5Test' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement one `UnifiedOperatorEngine` loop**

The loop must follow:

```text
observe -> infer budget -> plan/reuse -> execute -> verify -> learn/recover -> continue
```

It may run a micro-plan locally only while each intermediate postcondition is verified. Divergence aborts the remaining micro-plan before the next action.

- [ ] **Step 5: Change `TaskSessionEngine` step limits into rolling checkpoint controls for `UNTIL_USER_STOP`**

Keep ordinary one-shot/goal-complete budgets. For user-stop sessions, increment rolling epoch/checkpoint counters without returning `STEP_LIMIT` solely because cumulative steps exceed 1000. Preserve per-state recovery limits.

- [ ] **Step 6: Make `AgentConnectionManager` delegate task continuation to `UnifiedOperatorEngine`**

The WebSocket/polling layer continues to transport task start/cancel/checkpoint/reasoning responses; it does not plan individual familiar actions.

- [ ] **Step 7: Run V5 loop tests plus V4 regressions**

```bash
gradle testDebugUnitTest --tests '*UnifiedOperatorEngineTest' --tests '*PersistentLoopV5Test' --tests '*TaskSessionEngine*' --tests '*TaskResumeV4Test' --stacktrace
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/UnifiedOperatorEngine.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskSessionEngine.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent
git commit -m "feat(android-v5): add unified local operator loop"
```

---

### Task 9: Extend Gateway Task Protocol for Persistent Sessions and Cloud Escalation

**Files:**
- Modify: `android-agent-gateway/src/task-intent.js`
- Modify: `android-agent-gateway/src/device-session.js`
- Modify: `android-agent-gateway/src/index.js`
- Modify: `android-agent-gateway/src/planner.js`
- Test: `android-agent-gateway/test/task-intent-v5.test.mjs`
- Test: `android-agent-gateway/test/persistent-session-v5.test.mjs`
- Test: `android-agent-gateway/test/cloud-escalation-v5.test.mjs`

**Interfaces:**
- Consumes: natural-language goal, task ID, device checkpoint, optional compact observation.
- Produces: `persistencePolicy`, `allowedPackages`, cancel state, micro-plan/recovery response, and task status without raw private screen data.

- [ ] **Step 1: Write failing intent tests**

```js
test('play until I say stop maps to persistent user-stop policy', () => {
  const intent = interpretTaskIntent('Play this game until I tell you to stop')
  assert.equal(intent.persistencePolicy.includes('UNTIL_USER_STOP'), true)
  assert.equal(intent.persistencePolicy.includes('UNTIL_APP_SCOPE_EXIT'), true)
})
```

- [ ] **Step 2: Write failing cancel and escalation tests**

```js
test('cancel marks task and pushes cancellation', async () => {
  const session = makeSession()
  const task = session.createTask({ goal: 'play', persistencePolicy: ['UNTIL_USER_STOP'] })
  await session.cancelTask(task.taskId)
  assert.equal(session.getTask(task.taskId).status, 'CANCELLED')
})

test('micro-plan response is bounded to eight actions', async () => {
  const response = await planMicroActions(fakeContext())
  assert.ok(response.actions.length <= 8)
})
```

- [ ] **Step 3: Run gateway tests to RED**

```bash
cd android-agent-gateway
npm test
```

Expected: new V5 tests FAIL.

- [ ] **Step 4: Extend task intent and Durable Object state**

Persist only task metadata, allowed packages, policy, checkpoint counters, selected skill ID, sanitized action/result metadata, and sanitized error codes. Do not persist raw screenshot or raw private UI tree.

- [ ] **Step 5: Add protected endpoints for cancel/checkpoint/micro-plan/recovery**

Keep existing auth rules. New control endpoints require the same trusted control auth as existing task control. Device-facing checkpoint/result endpoints require device token binding.

- [ ] **Step 6: Run gateway tests to GREEN**

```bash
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-agent-gateway/src android-agent-gateway/test
git commit -m "feat(android-v5): extend persistent task protocol"
```

---

### Task 10: Add Android Gateway Client Methods and Offline-Safe Continuation

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/CommandSocketProtocol.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/network/V5GatewayClientContractTest.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/network/OfflineContinuationPolicyTest.kt`

**Interfaces:**
- Consumes: V5 gateway endpoints and WebSocket messages.
- Produces: task start/cancel/reasoning/checkpoint operations and local continuation policy.

- [ ] **Step 1: Write failing offline-continuation test**

```kotlin
@Test fun locallyAuthorizedKnownPath_continuesDuringTemporaryCloudLoss() {
    val policy = OfflineContinuationPolicy()
    assertTrue(policy.mayContinue(
        alreadyAuthorized = true,
        withinAllowedPackage = true,
        localConfidence = 0.95,
        cloudReasoningRequired = false,
        confirmationPending = false,
    ))
}
```

- [ ] **Step 2: Write failing unsafe-offline pause test**

```kotlin
@Test fun cloudReasoningRequired_pausesOffline() {
    val policy = OfflineContinuationPolicy()
    assertFalse(policy.mayContinue(true, true, 0.95, true, false))
}
```

- [ ] **Step 3: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*V5GatewayClientContractTest' --tests '*OfflineContinuationPolicyTest' --stacktrace
```

Expected: FAIL.

- [ ] **Step 4: Implement gateway methods and socket message decoding**

Add explicit methods for cancel, checkpoint, micro-plan request, recovery request, and task status. Do not reuse an ambiguous generic raw endpoint caller.

- [ ] **Step 5: Implement offline-safe continuation policy**

The local engine may continue only when all five conditions from the spec are true: already authorized, inside allowed package scope, sufficient local confidence, no cloud-only reasoning need, and no pending confirmation.

- [ ] **Step 6: Run focused and existing network tests**

```bash
gradle testDebugUnitTest --tests '*V5GatewayClientContractTest' --tests '*OfflineContinuationPolicyTest' --tests '*CommandSocketProtocolTest' --tests '*ConnectionCadenceTest' --stacktrace
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/network
git commit -m "feat(android-v5): add persistent gateway client contract"
```

---

### Task 11: Convert 2048 into a Local Reference Workload with Auto-Restart

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Session.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Solver.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/skills/game2048/Game2048ContinuousSessionV5Test.kt`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/skills/game2048/Game2048TimingV5Test.kt`

**Interfaces:**
- Consumes: board extractor result, adaptive scheduler, local session cancellation/app-scope status.
- Produces: legal swipe action, restart action on terminal state, domain verification token.

- [ ] **Step 1: Write failing auto-restart test**

```kotlin
@Test fun gameOver_requestsRestartInsteadOfCompletingPersistentTask() {
    val session = Game2048Session()
    val decision = session.nextPersistent(terminalBoard(), fingerprint = "x", region = boardRegion(), userStop = false)
    assertTrue(decision is Game2048Decision.Restart)
}
```

- [ ] **Step 2: Write failing fast-gesture test**

```kotlin
@Test fun localSwipe_usesAdaptiveFastDuration() {
    val session = Game2048Session()
    val action = session.next(nonTerminalBoard(), "fp1", boardRegion()) as Game2048Decision.Act
    assertTrue(action.action.durationMs in 60L..120L)
}
```

- [ ] **Step 3: Run 2048 tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*Game2048*' --stacktrace
```

Expected: new V5 tests FAIL.

- [ ] **Step 4: Remove the hard-coded 220 ms decision from `Game2048Session`**

The session requests timing from `AdaptiveActionScheduler`; it does not own a universal timing constant.

- [ ] **Step 5: Add persistent terminal handling**

Terminal board state returns a restart intent for a persistent game session. Restart must target only a verified `Try Again` / `New Game` control inside the same package and must re-observe a fresh board before resuming solver actions.

- [ ] **Step 6: Keep ad/purchase/external-link/account controls forbidden**

The 2048 skill never broadens task capability scope and never follows an unrelated overlay into another app.

- [ ] **Step 7: Run all 2048 and risk regression tests**

```bash
gradle testDebugUnitTest --tests '*Game2048*' --tests '*RiskPolicyTest' --stacktrace
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048 \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/skills/game2048
git commit -m "feat(android-v5): make 2048 a continuous local workload"
```

---

### Task 12: Migrate V4 App Skill Memory into V5 Mapping Candidates

**Files:**
- Modify: `android-agent-gateway/src/app-skill-memory.js`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/V4SkillMigration.kt`
- Test: `android-agent-gateway/test/app-skill-memory-v5.test.mjs`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/V4SkillMigrationTest.kt`

**Interfaces:**
- Consumes: V4 app-skill record and current V5 app observation.
- Produces: low/medium-confidence candidate screen/transition knowledge that requires re-verification before high-confidence reuse.

- [ ] **Step 1: Write failing migration test**

```kotlin
@Test fun oldCoordinateRecipe_neverBecomesTrustedTransition() {
    val candidate = V4SkillMigration().migrate(v4CoordinateRecipe())
    assertTrue(candidate.confidence < 0.8)
    assertTrue(candidate.requiresRegrounding)
}
```

- [ ] **Step 2: Write gateway memory non-authority test**

```js
test('v4 memory is a hint and cannot widen risk', () => {
  const migrated = migrateV4Skill({ riskClass: 'C', confidence: 1 })
  assert.equal(migrated.authority, 'HINT_ONLY')
  assert.equal(migrated.requiresCurrentAuthorization, true)
})
```

- [ ] **Step 3: Run Android and gateway tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*V4SkillMigrationTest' --stacktrace
cd ../android-agent-gateway
npm test
```

Expected: new migration tests FAIL.

- [ ] **Step 4: Implement bounded migration**

Never convert an old coordinate macro into unconditional execution. Semantic/visual anchors must re-ground against current UI before any candidate becomes a verified graph edge.

- [ ] **Step 5: Run migration tests to GREEN**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*V4SkillMigrationTest' --stacktrace
cd ../android-agent-gateway
npm test
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/mapping/V4SkillMigration.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/mapping/V4SkillMigrationTest.kt \
        android-agent-gateway/src/app-skill-memory.js \
        android-agent-gateway/test/app-skill-memory-v5.test.mjs
git commit -m "feat(android-v5): migrate v4 app skills as regrounded hints"
```

---

### Task 13: Add Cancellation, App-Scope Exit, and Operational Metrics

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/UnifiedOperatorEngine.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt`
- Modify: `android-agent-gateway/src/device-session.js`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/CancellationV5Test.kt`
- Test: `android-agent-gateway/test/observability-v5.test.mjs`

**Interfaces:**
- Consumes: cancel socket event, current foreground package, action/verifier timings.
- Produces: prompt local cancellation and sanitized metrics.

- [ ] **Step 1: Write failing cancellation test**

```kotlin
@Test fun cancellation_abortsBeforeNextNonAtomicAction() {
    val engine = cancellableTestEngine()
    engine.requestCancel()
    val decision = engine.nextDecision()
    assertEquals("CANCELLED", decision.code)
}
```

- [ ] **Step 2: Write failing app-scope exit test**

```kotlin
@Test fun targetAppExit_terminatesSingleAppPersistentSession() {
    val engine = testEngine(allowedPackages = setOf("com.example.game"))
    engine.observePackage("com.android.launcher")
    assertTrue(engine.currentSession().terminal)
}
```

- [ ] **Step 3: Write gateway metric privacy test**

```js
test('operational metrics exclude raw private content', () => {
  const metrics = sanitizeMetrics({ localDecisionLatencyMs: 12, screenshot: 'data:image/png;base64,secret' })
  assert.equal(metrics.screenshot, undefined)
  assert.equal(metrics.localDecisionLatencyMs, 12)
})
```

- [ ] **Step 4: Run focused tests to RED**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*CancellationV5Test' --stacktrace
cd ../android-agent-gateway
npm test
```

Expected: new tests FAIL.

- [ ] **Step 5: Implement cancellation and metrics**

Record only bounded operational values: local decision latency, action dispatch latency, action-to-event latency, verifier latency, local-vs-cloud reasoning counts, map/skill hit rates, recovery rate, screenshot rate, and cancellation latency. Never include screenshots, hidden reasoning, credentials, or private message bodies.

- [ ] **Step 6: Run focused tests to GREEN**

```bash
cd android-brain-agent
gradle testDebugUnitTest --tests '*CancellationV5Test' --stacktrace
cd ../android-agent-gateway
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/UnifiedOperatorEngine.kt \
        android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/CancellationV5Test.kt \
        android-agent-gateway/src/device-session.js \
        android-agent-gateway/test/observability-v5.test.mjs
git commit -m "feat(android-v5): add cancellation and safe observability"
```

---

### Task 14: Version V5, Remove Duplicate Command-Bridge Behavior, and Run Full Security Regression

**Files:**
- Modify: `android-brain-agent/app/build.gradle.kts`
- Modify: `.github/workflows/android-brain-agent-ci.yml`
- Modify or remove after consolidation: `.github/workflows/android-brain-agent-command-v4.yml`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/ReleaseIdentityV5Test.kt`
- Test: `android-agent-gateway/test/security-v5-regression.test.mjs`

**Interfaces:**
- Consumes: completed Android/gateway V5 implementation.
- Produces: one authoritative issue command bridge, release identity 0.5.0/14, and CI covering Android/gateway/security.

- [ ] **Step 1: Write failing release identity test**

```kotlin
@Test fun releaseIdentity_isV5() {
    assertEquals("0.5.0", BuildConfig.VERSION_NAME)
    assertEquals(14, BuildConfig.VERSION_CODE)
}
```

- [ ] **Step 2: Write gateway security regression assertions**

```js
test('persistent V5 cannot downgrade class C or class D', () => {
  assert.equal(effectiveRisk({ requested: 'C', learned: 'A' }), 'C')
  assert.equal(isAllowedUnattended('D'), false)
})
```

- [ ] **Step 3: Update version**

In `android-brain-agent/app/build.gradle.kts`:

```kotlin
versionCode = 14
versionName = "0.5.0"
```

- [ ] **Step 4: Consolidate the issue dispatcher**

There must be exactly one `[ANDROID_AGENT]` issue dispatcher. Keep the corrected OIDC audience `android-brain-agent-gateway`, route `GET /v1/device/latest`, authenticated status reads, `/v1/device/{id}/run`, command result `/commands/{id}/result`, and task result `/tasks/{taskId}`. Remove/disable the obsolete duplicate job so one issue cannot launch two conflicting workflows.

- [ ] **Step 5: Run full local CI commands**

```bash
cd android-brain-agent
gradle testDebugUnitTest lintDebug assembleDebug assembleRelease --stacktrace
cd ../android-agent-gateway
npm install --no-package-lock --ignore-scripts
npm test
npx wrangler deploy --dry-run
```

Expected: all commands PASS.

- [ ] **Step 6: Commit**

```bash
git add android-brain-agent/app/build.gradle.kts \
        android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/ReleaseIdentityV5Test.kt \
        android-agent-gateway/test/security-v5-regression.test.mjs \
        .github/workflows/android-brain-agent-ci.yml \
        .github/workflows/android-brain-agent-command-v4.yml
git commit -m "chore(android-v5): finalize release identity and command bridge"
```

---

### Task 15: CI, Merge, Exact-Main Deployment Verification, and Physical-Device Acceptance

**Files:**
- Create: `docs/android-agent/V5_ACCEPTANCE_CHECKLIST.md`
- Create: `docs/android-agent/V5_ACCEPTANCE_RESULTS.md`
- Modify only if evidence exposes a defect: relevant implementation/test files from Tasks 1–14.

**Interfaces:**
- Consumes: V5 branch/PR, GitHub Actions, production Cloudflare gateway, paired physical device.
- Produces: release evidence separating CI success, exact-main production deployment, `DEVICE_EXECUTED`, and physical `VERIFIED` acceptance.

- [ ] **Step 1: Write the acceptance checklist before running device tests**

The checklist must contain these exact cases:

```text
A. Standard semantic app: identify package, map >=3 screens, reuse learned path, recover one moved control.
B. Deep menu/settings flow: >10 actions, graph transitions, final-state verification, checkpoint/resume.
C. WebView/browser: sparse tree -> visual support -> verified action without false NO_OP.
D. Canvas/game 2048: local state loop, >100 actions, no per-move cloud, Game Over restart, repeated play, stop command, app-exit stop.
E. Persistent workload: >1000 actions without STEP_LIMIT, bounded recovery/checkpoints, prompt cancellation.
F. App mapping: unfamiliar app creates AppProfile/screens/transitions, reuses one path, confidence decays after changed UI/version.
G. Network degradation: locally solvable task continues temporarily; cloud-required state pauses safely; reconnect preserves task identity.
H. Safety: delete/purchase/send remain confirmation-gated; credential/OTP/private key denied; secure-window restrictions preserved.
```

- [ ] **Step 2: Push the implementation branch and open a PR**

Use a branch dedicated to V5 implementation. PR body must link the spec and this plan and state that physical-device acceptance remains pending until after exact-main deployment.

- [ ] **Step 3: Verify PR CI**

Require Android test/lint/build and gateway test/dry-run jobs to pass. Do not merge while any required check is red.

- [ ] **Step 4: Merge and capture exact main SHA**

Record the merge SHA in `V5_ACCEPTANCE_RESULTS.md` under `sourceMainSha`.

- [ ] **Step 5: Verify exact-main gateway deployment**

Confirm production `/health` reports the same `sourceSha` as merged `main`, task schema remains compatible, and V5 capability flags expected by the new tests are present. If production does not converge to exact main, stop acceptance and fix deployment first.

- [ ] **Step 6: Build/download the release APK from the exact-main workflow artifact**

Verify the artifact corresponds to the exact main SHA before installation. Signing/release packaging must preserve the current approved signer chain; if signer continuity cannot be proven, do not call it an in-place upgrade.

- [ ] **Step 7: Run physical acceptance cases A–H**

For every case record:

```text
caseId
exactMainSha
deviceId
appPackage(s)
startTime
endTime
QUEUED evidence
DEVICE_EXECUTED evidence
VERIFIED postcondition evidence
observed latency summary
result PASS/FAIL
sanitized failure code if any
```

Do not record raw screenshots/private UI text in GitHub acceptance docs.

- [ ] **Step 8: Enforce V5 completion gate**

V5 may be reported as `VERIFIED` only when all required cases A–H pass on the physical device. If CI/deploy passes but device acceptance is incomplete, report `DEPLOYED / PHYSICAL_ACCEPTANCE_PENDING`, not `VERIFIED`.

- [ ] **Step 9: Commit sanitized acceptance results**

```bash
git add docs/android-agent/V5_ACCEPTANCE_CHECKLIST.md docs/android-agent/V5_ACCEPTANCE_RESULTS.md
git commit -m "docs(android-v5): record physical acceptance evidence"
```

---

## Dependency Order

Execute tasks in this order because later interfaces depend on earlier contracts:

```text
1 contracts
  -> 2 perception
  -> 3 verification
  -> 4 inference/micro-plan
  -> 5 app mapping
  -> 6 exploration/recovery
  -> 7 action timing
  -> 8 unified local loop
  -> 9 gateway protocol
  -> 10 Android gateway/offline continuation
  -> 11 2048 reference workload
  -> 12 V4 memory migration
  -> 13 cancellation/metrics
  -> 14 release/CI/security
  -> 15 exact-main + physical acceptance
```

Tasks 5, 6, and 7 are logically independent after Tasks 1–4, but keep the sequence above for simpler review and lower merge-conflict risk.

## Final Verification Commands Before Merge

```bash
cd android-brain-agent
gradle testDebugUnitTest lintDebug assembleDebug assembleRelease --stacktrace
cd ../android-agent-gateway
npm install --no-package-lock --ignore-scripts
npm test
npx wrangler deploy --dry-run
```

Expected: all commands exit `0`; Android unit tests and lint are green; debug/release APKs are produced; all gateway tests pass; Wrangler dry-run succeeds.

## Plan Self-Review

- **Spec coverage:** Tasks 1–15 cover unified observation, event-driven cache, dynamic inference, micro-plans, multimodal verification, adaptive gesture timing, Universal App Mapping, confidence decay, safe exploration, graph reuse, recovery, persistent sessions, cancellation/app-scope exit, offline-safe continuation, 2048 auto-restart, V4 migration, privacy/observability, risk regression, command-bridge consolidation, exact-main deployment, and physical-device acceptance.
- **Placeholder scan:** No `TBD`, `TODO`, “implement later”, generic “add error handling”, or undefined follow-up task remains in the plan.
- **Type consistency:** `PersistencePolicy`, `PersistentOperatorSession`, `UnifiedObservation`, `VerificationResult`, `InferenceDirective`, `MicroPlan`, `TransitionEdge`, `ActionTiming`, and `UnifiedOperatorEngine` are defined before later tasks consume them.
- **Safety consistency:** No task lowers V4 risk or device-trust requirements; Class C remains task-bound confirmation and Class D remains denied.
- **Completion consistency:** CI/deployment success is explicitly separated from physical-device `VERIFIED` evidence.
