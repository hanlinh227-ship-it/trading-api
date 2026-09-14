# Android Brain Agent V4 Universal Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Android Brain Agent 0.3.3 into V4: a task-first natural-language Android operator with negation-aware intent, long-horizon checkpointed execution, hybrid semantic/visual control, reusable app skills, and a deterministic 2048 fast path.

**Architecture:** Preserve the single APK + Cloudflare Durable Object gateway. Move long/multi-step goals from legacy schema-1 `/commands` to schema-2 `/tasks`; interpret natural language into structured task intent before risk classification; run task sessions in bounded epochs; use Accessibility as primary perception and screenshots as visual fallback; keep the persistent device WebSocket in the per-action loop. Deterministic adapters such as 2048 execute locally/cheaply while the cloud planner remains the general fallback.

**Tech Stack:** Kotlin/JVM 17 Android app, Android AccessibilityService, OkHttp/WebSocket, Cloudflare Workers/Durable Objects, JavaScript Node test runner, GitHub Actions, Gradle 8.10.2.

**Spec:** `docs/superpowers/specs/2026-09-15-android-brain-agent-v4-universal-operator-design.md`

## Global Constraints

- applicationId remains `com.hanlinh.androidbrain`.
- V4 release is `versionCode = 13`, `versionName = "0.4.0"`.
- No root, raw shell, hidden ADB execution, Shizuku dependency, arbitrary script engine, security bypass, credential extraction, wallet signing, or financial mutation.
- Class C requires explicit confirmation bound to the exact task ID; Class D is denied.
- Password/PIN/OTP/private-key/recovery content and raw screenshots/private UI trees never enter public GitHub logs.
- External repositories are evidence/reference; no production source reuse from license-restricted OpenGUI/AppAgentX intake.
- Long execution is bounded: 50 actions/epoch, 20 ordinary epochs, five consecutive recoveries per unresolved state; continuation requires measurable progress.
- Schema 1 remains backward-compatible for safe one-shot commands; schema 2 is canonical for multi-step/long-running tasks.

---

### Task 1: Intent interpretation and route selection

**Files:**
- Create: `android-agent-gateway/src/task-intent.js`
- Test: `android-agent-gateway/test/task-intent-v4.test.mjs`
- Modify: `android-agent-gateway/src/tools.js`

**Interfaces:**
- Produces `interpretTaskIntent(goal, requestedScope?) -> TaskIntent`.
- Produces `shouldUseTaskPath(intent) -> boolean`.
- `classifyGoal(goal)` becomes a compatibility adapter over structured intent, not raw substring matching.

- [ ] **Step 1: Write failing tests** for negated purchase/delete/send clauses, explicit Class-C requests, Class-D requests, 2048/"until complete" long-running mode, and one-shot Settings navigation.
- [ ] **Step 2: Run gateway tests and verify RED** because `task-intent.js` and structured semantics do not exist.
- [ ] **Step 3: Implement minimal interpreter** that extracts forbidden actions before requested-action risk, recognizes long-running/repetitive/game intent, derives persistence/mode/capability scope, and retains deterministic Class-D denial.
- [ ] **Step 4: Run gateway tests and verify GREEN** including existing `tools.test.mjs`.
- [ ] **Step 5: Commit** intent interpreter and tests.

### Task 2: Task-aware GitHub/ChatGPT bridge and task lifecycle endpoints

**Files:**
- Modify: `.github/workflows/android-brain-agent-ci.yml`
- Modify: `android-agent-gateway/src/index.js`
- Modify: `android-agent-gateway/src/device-session.js`
- Test: `android-agent-gateway/test/index-v4.test.mjs`
- Test: `android-agent-gateway/test/task-lifecycle-v4.test.mjs`

**Interfaces:**
- `POST /v1/device/:deviceId/tasks` accepts natural-language goal and structured intent-derived scope.
- `POST /v1/device/:deviceId/tasks/:taskId/confirm` binds Class-C confirmation to the exact task.
- `POST /v1/device/:deviceId/tasks/:taskId/cancel` terminally cancels a task.
- Issue bridge routes long/multi-step/game/repetitive requests to `/tasks`; only verified one-shot A/B-safe commands may use `/commands`.

- [ ] **Step 1: Write failing endpoint/bridge tests** for task route selection, cancel, confirm binding, and sanitized status output.
- [ ] **Step 2: Verify RED** in CI/local Node tests.
- [ ] **Step 3: Implement task-aware routes and bridge shell logic** without placing GitHub Actions inside the per-step execution loop.
- [ ] **Step 4: Verify GREEN** and confirm legacy schema-1 tests still pass.
- [ ] **Step 5: Commit** bridge/lifecycle changes.

### Task 3: Epoch-based long-horizon task policy

**Files:**
- Modify: `android-agent-gateway/src/task-policy.js`
- Modify: `android-agent-gateway/src/device-session.js`
- Test: `android-agent-gateway/test/task-policy.test.mjs`
- Test: `android-agent-gateway/test/task-epochs-v4.test.mjs`

**Interfaces:**
- `TaskState` adds `epoch`, `epochStepCount`, `checkpointCount`, `progressMarker`, `persistence`.
- `recordTaskProgress` checkpoints after 50 actions; ordinary tasks cap at 20 epochs; five same-state recoveries remain the fail-closed limit.
- `UNTIL_TERMINAL` continuation still requires progress evidence and unchanged risk/capability scope.

- [ ] **Step 1: Replace the old 40-step regression with failing epoch tests** including >100 actions across checkpoints.
- [ ] **Step 2: Verify RED** because current policy throws after 40 steps.
- [ ] **Step 3: Implement epoch/checkpoint progression** and sanitized public state.
- [ ] **Step 4: Verify GREEN** for >100 actions, epoch cap, recovery cap, cancellation, and persistence.
- [ ] **Step 5: Commit** task-policy changes.

### Task 4: V4 action grammar and Android executor parity

**Files:**
- Modify: `android-agent-gateway/src/action-schema.js`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/Action.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/TypedActionCodec.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt`
- Test: `android-agent-gateway/test/action-schema-v4.test.mjs`
- Test: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/protocol/TypedActionCodecV4Test.kt`

**Interfaces:**
- Add typed `drag`, `multi_stroke_gesture`, `replace_text`, `clipboard_set`, `clipboard_paste` actions.
- Each action has one capability and fixed minimum risk metadata; Android codec names exactly match gateway schema.

- [ ] **Step 1: Write failing gateway/Kotlin codec tests** for every new action and malformed bounds/duration/stroke input.
- [ ] **Step 2: Verify RED** via Node/Gradle CI.
- [ ] **Step 3: Add schema + Kotlin sealed-action + codec + Accessibility dispatch implementations** with explicit unsupported/failure results where platform APIs cannot satisfy a primitive.
- [ ] **Step 4: Verify GREEN** and all legacy action tests.
- [ ] **Step 5: Commit** action parity.

### Task 5: Hybrid perception, mode routing, and verifier support

**Files:**
- Create: `android-agent-gateway/src/mode-router.js`
- Modify: `android-agent-gateway/src/planner.js`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/perception/AccessibilitySnapshot.kt` or the existing snapshot model file resolved in source.
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/Verifier.kt`
- Test: `android-agent-gateway/test/mode-router-v4.test.mjs`
- Test: Android perception/verifier tests under their existing package directories.

**Interfaces:**
- `selectExecutionMode(intent, observation) -> SEMANTIC|VISUAL|HYBRID|DETERMINISTIC`.
- Observation adds orientation/display metadata plus screenshot/region hash metadata, while private pixels remain transient.
- Visual fallback activates when semantic nodes are absent/insufficient for a visual/game task.

- [ ] **Step 1: Write failing mode/perception/verifier tests** for Canvas/WebView/game fallback, semantic preference, and redaction.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Implement mode router and observation metadata** using existing screenshot provider; keep raw image data ephemeral.
- [ ] **Step 4: Verify GREEN** including existing sensitive-redaction tests.
- [ ] **Step 5: Commit** hybrid perception.

### Task 6: AppSkillMemory with current-UI re-grounding

**Files:**
- Create: `android-agent-gateway/src/app-skill-memory.js`
- Test: `android-agent-gateway/test/app-skill-memory-v4.test.mjs`

**Interfaces:**
- `candidateFromTrajectory(task, history) -> AppSkill|null` only from successful non-Class-C/D trajectories.
- `groundSkill(skill, observation) -> grounded actions|null`; stale/missing anchors return null rather than blind replay.

- [ ] **Step 1: Write failing tests** for app scope, re-grounding, stale recipe fallback, and Class-C/D non-learning.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Implement bounded app-scoped recipes** stored in Durable Object-compatible JSON data.
- [ ] **Step 4: Verify GREEN**.
- [ ] **Step 5: Commit** app-skill memory.

### Task 7: Deterministic 2048 solver and game fast path

**Files:**
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Board.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Solver.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/skills/game2048/Game2048Session.kt`
- Create tests under `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/skills/game2048/`.
- Modify the existing task/execution dispatcher to invoke the deterministic adapter only for recognized 2048 intent.

**Interfaces:**
- `Game2048Board.move(Direction)` returns deterministic moved board + merge score and rejects no-op moves.
- `Game2048Solver.bestMove(board)` chooses only a legal move using empty-cells, monotonicity, smoothness, merge potential, and corner stability.
- `Game2048Session` emits one bounded swipe and waits for a changed visual board before continuing.

- [ ] **Step 1: Write failing board mechanics/solver tests** for all four directions, legal-move filtering, game-over, corner preference, and high-tile preservation.
- [ ] **Step 2: Verify RED** via Gradle.
- [ ] **Step 3: Implement board + expectimax/heuristic solver + session adapter** independent of external source code.
- [ ] **Step 4: Verify GREEN**, including a seeded full simulated game reaching a valid terminal state without illegal moves.
- [ ] **Step 5: Commit** deterministic game path.

### Task 8: Android long-horizon session parity, reconnect/resume, and release version

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskProgress.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/TaskSessionEngine.kt`
- Modify relevant `network`/`service` connection manager resolved from the current tree.
- Modify: `android-brain-agent/app/build.gradle.kts`
- Test: existing + new agent/network tests.

**Interfaces:**
- Android task progress mirrors epoch/checkpoint state.
- WebSocket reconnect resumes by task ID/checkpoint and never replays an already-receipted command ID.
- Release version becomes 13 / 0.4.0.

- [ ] **Step 1: Write failing Android tests** for >100 steps, checkpoint transition, reconnect resume, duplicate receipt suppression, and cancellation.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Implement session parity/reconnect changes and version bump**.
- [ ] **Step 4: Verify GREEN** with `testDebugUnitTest lintDebug assembleDebug assembleRelease`.
- [ ] **Step 5: Commit** Android runtime/release changes.

### Task 9: Acceptance matrix, CI bridge verification, and documentation

**Files:**
- Create: `android-agent-gateway/test/v4-acceptance-matrix.test.mjs`
- Modify: `.github/workflows/android-brain-agent-ci.yml`
- Update: V4 design status and release notes/checkpoint files only after tests verify behavior.

**Interfaces:**
- Acceptance tests cover open/read/reversible-change/form/list/visual/recovery/reconnect/>100-action/2048 categories with synthetic replay where physical hardware is not required.
- Workflow emits distinct `TASK_QUEUED`, `DEVICE_EXECUTED`, `TASK_COMPLETED` states without logging observations.

- [ ] **Step 1: Add acceptance/replay tests and workflow assertions**.
- [ ] **Step 2: Run full branch CI** and fix only observed failures using systematic debugging.
- [ ] **Step 3: Open PR and verify Android, gateway, lint, dry-run, and artifact jobs pass**.
- [ ] **Step 4: Review diff/security/license boundaries**, then squash merge only with green CI.
- [ ] **Step 5: Verify exact-main post-merge deploy** reports the merged source SHA.

### Task 10: Signed APK and physical acceptance

**Files/Artifacts:**
- Exact-main unsigned release APK from GitHub Actions.
- Locally/private-sign exact-main APK using the existing persistent signer; never commit private key/password.

**Interfaces:**
- Signed APK certificate must match the established persistent release certificate.
- Physical acceptance must use the new 0.4.0 APK on the paired device.

- [ ] **Step 1: Download exact-main release artifact and independently verify artifact digest**.
- [ ] **Step 2: Sign with the persistent release identity and verify v2/v3 signature + certificate fingerprint**.
- [ ] **Step 3: Install/update on the physical phone; if Android reports the known old-debug signer mismatch, perform the one-time user-visible uninstall/reinstall path and re-pair/regrant permissions**.
- [ ] **Step 4: Run physical acceptance:** safe read/navigation, reversible setting, >100-action synthetic/long task, visual fallback, reconnect resume, and a full autonomous 2048 game.
- [ ] **Step 5: Report completion only if all acceptance criteria are verified; otherwise report the exact external/device blocker without claiming V4 complete.**
