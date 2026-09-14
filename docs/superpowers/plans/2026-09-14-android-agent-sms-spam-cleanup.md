# Android Agent SMS Spam Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Android Brain Agent inspect the current accessibility screen, drive safe UI navigation, and execute a user-confirmed Class-C spam-message cleanup without weakening existing security boundaries.

**Architecture:** Add generic screen-read, click, and long-click actions to the Android agent. Gateway keeps deletion as Class C and only queues it when an explicit confirmation flag is present; the signed command carries a dedicated destructive-confirmation capability that the device verifies before execution.

**Tech Stack:** Kotlin/Android AccessibilityService, JUnit 4, Cloudflare Worker JavaScript, Node test runner, GitHub Actions.

**Spec:** Existing Android Brain Agent V2 architecture and Class A/B/C/D policy.

## Global Constraints

- Class C deletion always requires explicit confirmation.
- Class D remains blocked.
- No raw shell, lock-screen bypass, OTP/password/private-key access, stealth, or anti-detection behavior.
- Password accessibility nodes remain redacted.
- Destructive confirmation is one command only and is covered by the gateway signature.

---

### Task 1: Failing tests for new UI primitives and confirmation

**Files:**
- Modify: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/agent/GoalParserTest.kt`
- Modify: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/policy/RiskPolicyTest.kt`
- Modify: `android-agent-gateway/test/tools.test.mjs`

- [ ] Add tests for `Đọc màn hình`, `Bấm <selector>`, and `Giữ <selector>` parsing.
- [ ] Add a test proving Class C stays blocked without confirmation and is allowed only with explicit confirmation.
- [ ] Add a gateway test proving `confirmedRiskClassC` is accepted but deletion still classifies as C.
- [ ] Run CI and verify RED.

### Task 2: Android action primitives and screen detail

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/protocol/Action.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/GoalParser.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/action/AccessibilityActions.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/agent/CommandDispatcher.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/policy/RiskPolicy.kt`

- [ ] Add `ReadScreen` and `LongClickNode`.
- [ ] Make click matching case-insensitive/fuzzy while still using accessibility nodes only.
- [ ] Return a compact redacted accessibility snapshot in `TaskResult.detail` for `ReadScreen`.
- [ ] Use effective risk = max(action risk, signed command risk).
- [ ] Require signed `ui.destructive.confirmed` scope before a Class-C command can execute.

### Task 3: Gateway one-shot Class-C confirmation

**Files:**
- Modify: `android-agent-gateway/src/tools.js`
- Modify: `android-agent-gateway/src/index.js`
- Modify: `.github/workflows/android-brain-agent-ci.yml`

- [ ] Accept `confirmedRiskClassC` in validated goal payloads.
- [ ] Keep Class C rejected by default.
- [ ] When explicit confirmation is true, add `ui.destructive.confirmed` to signed capability scope and queue Class C.
- [ ] Keep Class D blocked.
- [ ] Update issue-command validation to accept the confirmation flag.

### Task 4: Version, build, and E2E verification

**Files:**
- Modify: `android-brain-agent/app/build.gradle.kts`

- [ ] Bump to V2.2.
- [ ] Run Android tests, lint, APK build, gateway tests, and Wrangler dry-run in CI.
- [ ] Merge only after all checks pass.
- [ ] Download APK artifact.
- [ ] After installation, issue `Đọc màn hình` and use the returned accessibility tree to navigate specifically into the Messages spam folder.
- [ ] Execute destructive taps only with the already-authorized one-shot Class-C confirmation and verify postcondition.