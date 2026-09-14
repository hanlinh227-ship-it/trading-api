# Android Brain Agent V4 Universal Operator — Design

**Date:** 2026-09-15  
**Status:** User-approved architecture; written-spec review gate pending  
**Target:** Single sideloaded Android APK + existing Cloudflare gateway + GitHub/ChatGPT control bridge  
**Baseline:** Android Brain Agent `0.3.3` / versionCode 12 on `main` (`1fac5ba592ffe88205ab4bf9ea016f4cfdd42601`)

## 1. Product intent

V4 turns the current bounded Android operator into a **natural-language universal phone operator**.

The user should be able to say what they want in ordinary language, including broad goals such as:

- “Open Settings and change dark mode.”
- “Clean up these notifications.”
- “Open 2048 and keep playing for the highest score you can reach.”
- “Open this app, find the relevant item, fill the form, and finish the task.”
- “Do the repetitive steps until the work is finished.”

The system must infer the **task intent**, choose the appropriate observation/action strategy, execute the task over many steps, verify progress, recover from UI changes, and stop only on completion, explicit user cancellation, a hard safety boundary, or a verified inability to continue.

“Universal” means broad operation of ordinary user-accessible Android UI under permissions explicitly granted by the device owner. It does **not** mean root, security bypass, hidden privilege escalation, bypassing biometric/lock-screen protections, extracting credentials, or performing prohibited Class-D actions.

## 2. Root cause being fixed

V3 already contains a schema-2 task engine, typed actions, observation upload, planner, risk clamp, and WebSocket-capable device session. The main operational bottleneck is that the **GitHub issue command bridge still posts every request to the legacy `/commands` schema-1 path**.

This causes three concrete failures:

1. Long-running goals are treated like one-shot legacy commands instead of task sessions.
2. The legacy keyword risk classifier can misread negated text. For example, a goal containing “do not interact with purchases” still contains the token `purchase` and may be classified as Class C, returning HTTP 409.
3. V3 task progress is hard-limited to 40 steps, which is appropriate for bounded app workflows but not for games, repetitive automation, or workflows that legitimately require hundreds of actions.

V4 fixes the **bridge, intent model, execution horizon, visual fallback, and deterministic fast paths together**. No single patch is accepted as “universal control.”

## 3. Open-source research and fusion policy

External projects are capability/evidence inputs only. They do not become parallel reasoning authorities. Code reuse is allowed only when license status is compatible and provenance is preserved; otherwise the project is reference-only.

### 3.1 Minitap `mobile-use`

Repository: `minitap-ai/mobile-use`  
License: Apache-2.0  
Useful patterns:

- natural-language phone control;
- task decomposition / multi-agent execution;
- AndroidWorld-oriented evaluation;
- structured extraction;
- multiple model providers.

Important limitation explicitly documented upstream: games often expose little or no accessibility-tree data.

**V4 fusion:** adopt task decomposition and benchmark discipline; do not copy its ADB/local-runtime requirement into production. Use V4’s existing cloud-first gateway and Android Accessibility runtime.

### 3.2 Mobilerun

Repository: `droidrun/mobilerun`  
License: MIT  
Useful patterns:

- accessibility-tree + screenshot hybrid perception;
- screenshot-only / vision-only fallback;
- manager/executor reasoning mode for complex tasks;
- app-specific “cards” / reusable guidance;
- saved trajectories, tracing, structured output;
- Android Portal model for device-side control.

**V4 fusion:** directly inform the hybrid perception contract, app skill cards, execution traces, and manager/executor split. Production remains zero-local; no mandatory Python/ADB runtime.

### 3.3 AppAgent

Repository: `TencentQQGYLab/AppAgent`  
License: MIT  
Useful patterns:

- human-like tap/swipe action space;
- autonomous app exploration;
- learning from human demonstrations;
- generated app documentation/knowledge;
- coordinate-grid fallback when semantic labeling is insufficient.

**V4 fusion:** add app-learning memory and visual coordinate fallback. Learned macros are suggestions, never blindly trusted: they must be re-grounded against current UI state before execution.

### 3.4 AppAgentX

Repository: `Westlake-AGI-Lab/AppAgentX`  
License: no repository-root license verified during intake, therefore **reference-only** until license status is resolved.  
Useful patterns:

- task-execution memory;
- discovery of repeated low-level action sequences;
- evolution of high-level reusable actions / shortcuts.

**V4 fusion:** implement the concept independently: verified successful trajectories may produce app-scoped action recipes, but promotion requires replay/eval evidence and current-UI re-grounding.

### 3.5 OpenGUI

Repository: `Core-Mate/OpenGUI`  
License: Business Source License 1.1; production use is restricted before its change date. **Reference-only; no source-code copying into production.**  
Useful patterns:

- long-running task orchestration;
- plan supervisor + executor graph + summarizer;
- persistent standby WebSocket to Android client;
- separate planning and visual-execution model roles;
- asynchronous task status/cancel interface.

**V4 fusion:** independently implement equivalent architectural ideas using our existing Cloudflare Durable Object + WebSocket infrastructure.

### 3.6 AndroidWorld

Repository: `google-research/android_world`  
License: Apache-2.0  
Useful patterns:

- 116 reproducible tasks across 20 apps;
- screenshot + UI-element agent loop;
- per-task step budgets;
- durable task-success signals;
- checkpoint/resume evaluation.

**V4 fusion:** use AndroidWorld as a benchmark/eval reference, not as a production dependency. Create a compatible evaluation adapter for representative tasks where practical.

### 3.7 AutoJs6

Repository: `SuperMonster003/AutoJs6`  
License: MPL-2.0  
Useful patterns:

- broad on-device Accessibility-driven automation;
- mature selector/action scripting surface;
- long-running on-device automation concepts.

**V4 fusion:** reference its automation surface and selector ergonomics. Do not embed a general arbitrary-JavaScript engine in V4; that would unnecessarily expand attack surface, code size, and permission risk. Any direct MPL code reuse would require file-level source/license obligations and must be explicitly reviewed before use.

## 4. V4 architecture

### 4.1 Intent Interpreter

Natural language is converted into a structured `TaskIntent` before execution:

```text
TaskIntent
- objective
- completionCriteria[]
- forbiddenActions[]
- preferredApp / targetPackages[]
- executionMode: AUTO | SEMANTIC | VISUAL | DETERMINISTIC
- persistence: ONE_SHOT | LONG_RUNNING | UNTIL_TERMINAL
- capabilityScope[]
- riskCeiling
- classCConfirmationBinding
- userConstraints[]
```

The interpreter must understand negation and constraint semantics. Risk is **not** determined by substring matching alone.

Examples:

- “Do not buy anything” creates a `forbiddenActions=[PURCHASE]`; it does not raise the goal to Class C merely because the word “buy” appears.
- “Delete these 10 messages” is Class C because deletion is the requested action.
- “Open Messages and inspect spam” is Class A unless a later planned action mutates data.

The planner never receives permission merely because it inferred an action. Capability/risk authorization remains external and monotonic.

### 4.2 Mode Router

For every task, V4 selects one or more execution modes:

1. **Semantic UI mode** — Accessibility tree / resource IDs / roles / text. Primary mode for ordinary Android apps.
2. **Visual UI mode** — screenshot grounding for Canvas, WebView, SurfaceView, custom renderers, games, unlabeled icons, or missing Accessibility nodes.
3. **Deterministic skill mode** — local/app-specific solvers for well-defined domains such as 2048, calculator operations, grid puzzles, or repeated deterministic workflows.
4. **Hybrid mode** — semantic tree for navigation and screenshot/vision only where semantic information is insufficient.

Mode selection is reversible per step. Failure of one perception channel should not terminate the task if another safe channel remains available.

### 4.3 Observation Engine V4

Each observation may contain:

- foreground package/activity/window title;
- semantic Accessibility nodes;
- screen width/height/orientation;
- screenshot where Android permits it;
- screenshot perceptual hash / region hashes;
- current keyboard/IME state when observable;
- device orientation and basic display state;
- sanitized notification context when explicitly granted;
- optional local facts from contacts/files/app-specific resolvers;
- task-local transient visual features;
- deterministic observation fingerprint.

Privacy rules from V3 remain mandatory:

- password/PIN/OTP/private-key/recovery fields are redacted;
- secure-window screenshot failure is explicit;
- raw screenshots/private UI trees never go to public GitHub logs;
- minimum necessary context is sent to the cloud planner.

### 4.4 Action Engine V4

V4 preserves existing actions and adds missing generic primitives needed for broad phone operation:

- `launch_app`
- `open_url`
- `tap_node`, `long_click_node`
- `tap_point`, `long_press_point`, `double_tap_point`
- `swipe`
- `drag`
- `multi_stroke_gesture` for bounded multi-touch-compatible gestures where Accessibility permits them
- `scroll_node`
- `set_text`, `clear_text`
- `select_text` / `replace_text` where supported
- `clipboard_set` / `clipboard_paste` only when Android policy and foreground context permit it
- `global_back`, `global_home`, `global_recents`, `global_notifications`, `global_quick_settings`
- `wait`
- `observe`
- file-picker/navigation actions through normal user-visible Storage Access Framework surfaces

No raw shell, hidden ADB command, root command, arbitrary code execution, or arbitrary script engine is exposed as a planner action.

### 4.5 Long-Horizon TaskSessionEngine

Replace the single fixed 40-step ceiling with **bounded epochs**.

Default policy:

- up to 50 actions per epoch;
- checkpoint after every epoch and at meaningful subgoal completion;
- up to 20 epochs (1000 actions) for ordinary long-running tasks;
- `UNTIL_TERMINAL` tasks such as 2048 may continue across epochs while measurable progress exists;
- each epoch has no-op, repeated-state, timeout, and recovery budgets;
- maximum 5 consecutive recovery attempts for the same unresolved state;
- a task can extend to the next epoch only if progress is demonstrated and risk/capability scope is unchanged;
- kill switch/cancel takes effect immediately.

This removes the artificial 40-action bottleneck without creating unbounded runaway execution.

Task lifecycle:

```text
QUEUED
 -> OBSERVING
 -> DECOMPOSING
 -> PLANNING
 -> ACTING
 -> VERIFYING
 -> (PLANNING | RECOVERING | CHECKPOINTING)
 -> ...
 -> COMPLETED | FAILED | CANCELLED | BLOCKED_BY_USER
```

### 4.6 Goal Decomposer + Planner + Verifier

Use distinct roles rather than one model attempting everything:

- **Goal Decomposer:** converts the user objective into subgoals and completion criteria.
- **Action Planner:** chooses exactly one next typed action using current observation and bounded history.
- **Verifier:** checks the postcondition using semantic + visual evidence.
- **Recovery Planner:** chooses an alternative primitive/path after a verified no-op or layout mismatch.
- **Summarizer:** produces a compact final result without leaking private screen contents.

For simple deterministic tasks, these model calls are skipped.

### 4.7 Persistent device channel

The Android client keeps the existing reverse WebSocket/heartbeat design and promotes it to the primary task channel:

```text
ChatGPT / GitHub control
        ↓
Cloudflare Task API
        ↓
Durable Object task state
        ⇅ persistent WebSocket
Android Brain Agent
        ↓
Accessibility / screenshot / local resolver
```

GitHub Actions must not sit inside the per-action loop. GitHub is a trusted dispatch/audit entry point; the Cloudflare gateway and device WebSocket own the long-running execution session.

### 4.8 Bridge V4

The bridge becomes task-aware.

- one-shot supported legacy goals may still use `/commands`;
- natural-language multi-step, long-running, visual, game, repetitive, or “until complete” goals use `/tasks` automatically;
- the bridge returns `TASK_QUEUED` with a task ID rather than pretending a single command receipt means the entire task completed;
- status reads use `GET /tasks/:taskId`;
- Class-C confirmation is bound to the exact task ID;
- cancellation calls the task cancel path;
- bridge logs contain task state only, never raw observations/screenshots.

### 4.9 Risk and permission engine V4

Risk is derived from:

1. requested user intent;
2. actual planned action;
3. target/context semantics;
4. current permission scope.

Negated/forbidden actions are not promoted to requested actions.

Risk classes remain:

- **A:** observe/navigation/non-mutating control;
- **B:** typing, toggles, edits, reversible app-state changes;
- **C:** send/post/delete/uninstall/purchase/irreversible or externally consequential mutation; requires task-bound explicit confirmation;
- **D:** credentials/OTP/private key/security bypass/financial transfer or signing; denied unattended.

The planner cannot widen scope or lower effective risk.

## 5. App learning and reusable skills

V4 adds an `AppSkillMemory` inspired by AppAgent/AppAgentX and Mobilerun app cards.

A successful trajectory can produce a candidate recipe:

```text
AppSkill
- packageName
- intentPattern
- requiredCapabilities
- semanticAnchors[]
- visualAnchors[]
- actionTemplate[]
- preconditions[]
- postconditions[]
- successEvidence
- sourceVersion / appVersion hints
- confidence
```

Rules:

- recipes are app-scoped;
- no blind coordinate replay across changed UI;
- every step is re-grounded against the current observation;
- stale/failed recipes fall back to general planning;
- Class-C/D authority is never learned or promoted from repetition;
- promotion requires repeated successful replay/eval evidence.

## 6. Game Autopilot

Games are a first-class V4 use case because many games do not expose Accessibility trees.

### 6.1 Generic game path

Use screenshot-only or hybrid perception:

`capture -> identify playable region/state -> choose action -> gesture -> screen-diff verify -> repeat`

This is suitable for turn-based, puzzle, idle, menu-driven, and slower visual games. Real-time action games requiring high-frequency 30–60 FPS control remain outside the quality target of a cloud-planned agent unless a deterministic local adapter exists.

### 6.2 2048 adapter

2048 gets a deterministic local fast path:

1. detect/lock the 4×4 board region;
2. classify 16 tiles from screenshot colors/text/geometry;
3. build the board matrix;
4. validate the matrix against visual evidence;
5. use expectimax/heuristic search prioritizing monotonicity, empty cells, merge potential, smoothness, and stable-corner strategy;
6. emit only legal swipe directions;
7. verify board change after each swipe;
8. re-detect the board if layout/orientation changes;
9. continue across epochs until game-over or user cancellation;
10. report final score / highest tile when readable.

The fast path must not interact with ads, purchases, external links, or unrelated controls.

## 7. File, notification, messaging, and settings operations

Broad phone control is implemented through ordinary Android/UI capabilities rather than hidden privileged APIs:

- **Files:** Storage Access Framework / document picker + visible app UI.
- **Notifications:** Notification listener only after explicit grant; mutating actions use the relevant app/UI and risk policy.
- **Contacts:** local resolver through Android Contacts provider when permission is granted.
- **Messages/email/social:** navigation and drafting are allowed according to scope; sending/posting is Class C and requires task-bound confirmation.
- **Settings:** visible settings navigation/toggles; ordinary reversible toggles are Class B, security-sensitive state may escalate or be denied.
- **App install/uninstall:** user-visible installer/settings UI only; uninstall is Class C. Silent package management is not supported.

## 8. Reliability and recovery

V4 must handle:

- moved/missing nodes → re-observe/re-ground;
- custom-rendered UI → visual mode;
- stale screenshots → recapture;
- keyboard covering target → dismiss/replan;
- app unexpectedly changed → return to target only if policy permits;
- transient dialogs → treat as next state;
- action no-op → alternate primitive;
- repeated fingerprint → recovery counter;
- WebSocket interruption → reconnect and resume from checkpoint;
- device restart/app process death → task pauses and resumes only after state can be revalidated;
- model outage → deterministic/app-skill fallback where safe, otherwise fail explicitly.

A task must never claim success merely because an action was queued.

## 9. Observability

Persist only sanitized operational evidence:

- task ID;
- state transition;
- action type;
- postcondition result;
- timing/latency;
- recovery count;
- observation fingerprints/hashes;
- planner mode;
- app package;
- completion/failure code.

Do not persist hidden model reasoning, raw passwords, OTPs, private screenshots, raw message bodies, private keys, or raw contact lists in public logs.

## 10. Testing strategy

### 10.1 Unit tests

Mandatory regression coverage:

- negation-aware risk interpretation (`do not buy` != requested purchase);
- intent → task/command route selection;
- schema-2 typed action validation;
- action/risk/capability clamp;
- epoch/checkpoint progression;
- no-op and repeated-fingerprint recovery;
- WebSocket reconnect/resume;
- app-skill re-grounding;
- 2048 board parsing and legal-move solver;
- secure/private observation redaction.

### 10.2 Gateway tests

- `/tasks` create/status/cancel/confirm;
- exact device identity and signed action receipts;
- bridge creates task sessions for long-running goals;
- task checkpoints survive Durable Object persistence;
- Class-C confirmation cannot leak to another task;
- Class-D remains denied.

### 10.3 Android tests

- semantic observation;
- screenshot capture API 30+;
- gesture dispatch including drag/multi-stroke where supported;
- text/clipboard behavior with explicit failure states;
- foreground/app postcondition verification;
- process/service reconnect behavior.

### 10.4 Replay/trajectory tests

Store sanitized synthetic/replay observations for:

- Settings navigation;
- browser/WebView navigation;
- form filling;
- file picker;
- notification flow;
- message drafting;
- Canvas/game screen;
- changed-layout recovery.

### 10.5 AndroidWorld-inspired acceptance matrix

Build a smaller reproducible suite modeled after AndroidWorld categories. V4 is not considered “universal-ready” merely because one demo succeeds.

At minimum verify:

1. open/navigate an app;
2. read a setting/value;
3. change a reversible setting;
4. fill a form without sending;
5. scroll/search a long list;
6. operate a WebView/custom UI using visual fallback;
7. recover after a moved target;
8. survive gateway/device reconnect;
9. run a >100-action task across checkpoints;
10. play 2048 autonomously for a complete game.

## 11. Release and compatibility

Planned first V4 release:

- application ID unchanged: `com.hanlinh.androidbrain`;
- versionCode: **13**;
- versionName: **`0.4.0`**;
- same persistent release signing identity;
- schema 1 remains backward-compatible for safe one-shot commands;
- schema 2 becomes the canonical task/control path;
- V3 pairing data should remain valid on update where Android signature continuity permits.

## 12. Acceptance criteria

V4 is not complete until all of the following are true:

1. Plain-language goals are parsed into structured intent and constraints.
2. Negated forbidden actions do not trigger false risk escalation.
3. GitHub/ChatGPT bridge routes multi-step/long-running goals through `/tasks`, not legacy `/commands`.
4. Device can receive and continue a task over the persistent WebSocket without GitHub in the per-step loop.
5. Semantic and visual perception both work, with automatic fallback.
6. Long tasks can execute across bounded checkpoints beyond 40 actions without becoming unbounded.
7. Generic visual-game control works for non-realtime games where screenshots provide enough state.
8. 2048 has a deterministic solver/visual adapter and completes an autonomous game on the physical device.
9. AppSkillMemory can reuse a verified app workflow while re-grounding against current UI.
10. Existing V3 security guarantees do not regress.
11. Android unit/lint/release build and gateway test/dry-run all pass.
12. Exact-main gateway deploy is production-verified.
13. Signed release APK passes signature/integrity checks with the persistent signer.
14. Physical device acceptance matrix passes on the new APK.
15. No unresolved material license, permission, privacy, security, reconnect, task-loop, bridge, or release bottleneck remains when completion is reported.

## 13. Explicit non-goals / platform boundaries

V4 does not promise actions that a normal user-granted Android application cannot lawfully perform.

It does not:

- root the device or unlock the bootloader;
- silently grant itself Android permissions;
- bypass lockscreen, biometrics, secure-window restrictions, enterprise policy, or app security controls;
- extract passwords/PINs/OTP/private keys/recovery phrases;
- sign wallets or execute transfers/withdrawals/trades unattended;
- expose arbitrary shell/code execution to the cloud planner;
- guarantee high-skill realtime play for FPS/racing/rhythm games without a specialized local deterministic controller.

Within those boundaries, the target is **maximal practical Android UI autonomy** from natural-language intent.