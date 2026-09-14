# Android Agent Low-Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce perceived and device command latency by combining immediate chat acknowledgement, WebSocket push notification, 1-second polling fallback, and queue-only issue workflows.

**Architecture:** The gateway remains the signed-command authority. Android keeps retrieving commands from `/next`, but WebSocket `command_available` events trigger immediate retrieval; a 1-second poll is the fallback. The GitHub issue workflow stops waiting for device completion after queueing.

**Tech Stack:** Kotlin, Android Foreground Service, OkHttp WebSocket, JUnit 4, GitHub Actions, Cloudflare Workers.

**Spec:** `docs/superpowers/specs/2026-09-14-android-agent-low-latency-design.md`

## Global Constraints
- Preserve all existing signature, replay, risk-policy, kill-switch, and Class C/D safeguards.
- Do not add raw shell, lock/security bypass, OTP/credential handling, or hidden background mutation.
- WebSocket is notification-only; commands are still fetched from authenticated `/next`.
- Fallback polling interval is exactly 1 second.
- Android command chat responses fast-ACK after bridge issue creation; completion checks are on-demand.

---

### Task 1: Latency policy regression test

**Files:**
- Create: `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/network/ConnectionCadenceTest.kt`
- Create: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/ConnectionCadence.kt`

**Interfaces:**
- Produces: `ConnectionCadence.FALLBACK_POLL_MS: Long`, `ConnectionCadence.RECONNECT_MIN_MS: Long`, `ConnectionCadence.RECONNECT_MAX_MS: Long`.

- [ ] **Step 1: Write the failing test**

```kotlin
class ConnectionCadenceTest {
    @Test fun fallback_poll_is_one_second() {
        assertEquals(1_000L, ConnectionCadence.FALLBACK_POLL_MS)
    }

    @Test fun reconnect_backoff_is_bounded() {
        assertTrue(ConnectionCadence.RECONNECT_MIN_MS >= 500L)
        assertTrue(ConnectionCadence.RECONNECT_MAX_MS <= 30_000L)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `gradle testDebugUnitTest --tests '*ConnectionCadenceTest'`
Expected: FAIL because `ConnectionCadence` does not exist.

- [ ] **Step 3: Write minimal implementation**

```kotlin
object ConnectionCadence {
    const val FALLBACK_POLL_MS = 1_000L
    const val RECONNECT_MIN_MS = 1_000L
    const val RECONNECT_MAX_MS = 30_000L
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `gradle testDebugUnitTest --tests '*ConnectionCadenceTest'`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "test(android-agent): lock low-latency connection cadence"`

### Task 2: Push-first GatewayClient and connection manager

**Files:**
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt`
- Modify: `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt`

**Interfaces:**
- `GatewayClient.openCommandSocket(deviceId: String, token: String, listener: WebSocketListener): WebSocket`
- `AgentConnectionManager` uses one single-thread scheduled executor for socket-triggered pulls and fallback polling.

- [ ] **Step 1: Add WebSocket helper to GatewayClient**

Build URL from the existing base URL, convert `https` to `wss`, attach the existing bearer token, and call OkHttp `newWebSocket`.

- [ ] **Step 2: Convert AgentConnectionManager to push-first**

On start, open the socket and schedule 1-second fallback polling. On `command_available`, enqueue `pollOnce()` immediately. On socket failure or closure, reconnect with bounded exponential backoff while leaving fallback polling active.

- [ ] **Step 3: Run Android unit tests**

Run: `gradle testDebugUnitTest`
Expected: PASS.

- [ ] **Step 4: Commit**

`git commit -m "feat(android-agent): use push-first command pickup"`

### Task 3: Queue-only GitHub bridge and fast-ACK contract

**Files:**
- Modify: `.github/workflows/android-brain-agent-ci.yml`
- Modify: `AGENTS.md`

**Interfaces:**
- Issue workflow ends successfully once gateway returns `{queued:true, commandId}`.
- Android user-facing contract does not wait for workflow/device completion unless status verification is requested.

- [ ] **Step 1: Remove synchronous device completion loop from issue job**

After queueing, emit `ANDROID_AGENT_QUEUED=PASS` and the command ID. Do not poll `/status` in the issue-triggered run.

- [ ] **Step 2: Add fast-ACK interaction contract**

Add: “For Android Agent commands, create the command bridge issue and respond immediately after issue creation; do not wait for Actions/device completion unless the user asks to check status.”

- [ ] **Step 3: Run YAML/action validation through CI**

Expected: issue workflow still queues valid commands and exits quickly.

- [ ] **Step 4: Commit**

`git commit -m "perf(android-agent): fast-ack queued commands"`

### Task 4: Version, CI, merge, production verification

**Files:**
- Modify: `android-brain-agent/app/build.gradle.kts`

**Interfaces:**
- Version name: `0.2.3-alpha`
- Version code: `7`

- [ ] **Step 1: Bump version**
- [ ] **Step 2: Run `testDebugUnitTest lintDebug assembleDebug` and gateway tests in CI**
- [ ] **Step 3: Verify Android and gateway jobs are green**
- [ ] **Step 4: Merge to main**
- [ ] **Step 5: Verify production gateway exact main deployment succeeds**
- [ ] **Step 6: Fetch the debug APK artifact for installation**
