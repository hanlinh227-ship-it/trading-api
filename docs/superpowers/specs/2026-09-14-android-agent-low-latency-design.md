# Android Agent Low-Latency Design

**Status:** approved by standing user execution authorization on 2026-09-14.

## Goal
Make Android Brain Agent feel immediate: acknowledge a command in chat as soon as it has been handed to the command bridge, then minimize device execution latency after the gateway queues it.

## Root cause evidence
The current path is `ChatGPT -> GitHub issue -> GitHub Actions runner -> Cloudflare gateway -> Android poll -> result -> workflow verification`.

Observed latency contributors in the current implementation:
- `AgentConnectionManager` polls `/next` every 4 seconds even though the gateway already supports a WebSocket `/socket` endpoint and emits `command_available` when a command is queued.
- The issue-triggered workflow waits for up to 20 status checks with 3-second sleeps after queueing, which delays any caller that waits for full workflow completion.
- The GitHub issue bridge requires runner startup/OIDC; this cannot be eliminated without a new directly connected ChatGPT tool, so the user-facing contract must not synchronously wait for that runner to finish.

## Architecture
### 1. Immediate chat ACK
For Android device commands, ChatGPT creates the `[ANDROID_AGENT]` issue and returns immediately after the issue is created. It does not synchronously poll workflow completion unless the user asks for status/verification. This keeps conversational response latency bounded by the issue write rather than device execution.

### 2. Push-first device transport
`AgentConnectionManager` opens an authenticated OkHttp WebSocket to `/v1/device/{deviceId}/socket`.
- On `connected`, mark push transport healthy.
- On `command_available`, schedule `pollOnce()` immediately on the single-thread executor.
- On socket failure/close, keep a 1-second HTTP polling fallback and reconnect with bounded backoff.
- Keep all command retrieval through the existing authenticated `/next` endpoint so queue semantics, signature verification, replay prevention, and policy remain unchanged.

### 3. Bounded fallback polling
Change fallback polling from 4 seconds to 1 second. WebSocket remains preferred; polling is only the safety net. This bounds queue-to-device pickup to about 1 second even when push is unavailable.

### 4. Fast bridge workflow
The issue-triggered workflow becomes queue-first:
- validate payload;
- obtain GitHub OIDC token;
- resolve device;
- queue command;
- print `ANDROID_AGENT_QUEUED=PASS` and exit.
Full device-completion verification is removed from the synchronous issue job. Verification remains available through the gateway status endpoint when explicitly requested.

### 5. Reliability and safety
- No raw shell or permission widening.
- Class C/D policy remains unchanged.
- WebSocket only notifies availability; signed command retrieval still happens through `/next`.
- HTTP polling remains available if WebSocket is blocked by carrier/network conditions.
- The foreground service remains the lifecycle owner.
- Secrets/tokens are never logged.

## Success criteria
- Chat acknowledgement occurs immediately after issue creation rather than after workflow/device completion.
- When the gateway already has a command, a healthy WebSocket causes immediate retrieval without waiting for the polling interval.
- With WebSocket unavailable, fallback pickup interval is 1 second.
- Android unit tests, gateway tests, lint, APK build, and production gateway verification remain green.
- Existing V2.2 destructive-action safeguards remain intact.

## Files
- `AGENTS.md`: encode fast-ACK interaction contract for Android commands.
- `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/GatewayClient.kt`: authenticated WebSocket helper.
- `android-brain-agent/app/src/main/java/com/hanlinh/androidbrain/network/AgentConnectionManager.kt`: push-first connection and 1-second fallback.
- `android-brain-agent/app/src/test/java/com/hanlinh/androidbrain/network/ConnectionCadenceTest.kt`: latency policy regression tests.
- `.github/workflows/android-brain-agent-ci.yml`: stop synchronous post-queue verification for issue commands.
- `android-brain-agent/app/build.gradle.kts`: version bump for the latency release.
