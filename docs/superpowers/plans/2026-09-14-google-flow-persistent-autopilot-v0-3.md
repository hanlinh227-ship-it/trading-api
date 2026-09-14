# Google Flow Persistent Autopilot v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, fail-closed Chrome extension and GitHub command bus so later ChatGPT conversations can enqueue bounded Google Flow render jobs without storing browser credentials or requiring a paid browser-control service.

**Architecture:** Canonical source and documentation live on the feature branch and later `main`; routine render commands live on a dedicated `automation/google-flow-command-bus` branch at `automation/google_flow/queue.json`. The Manifest V3 extension polls that exact raw GitHub queue, deduplicates/validates commands, wakes with `chrome.alarms`, executes only calibrated Flow actions on allowlisted origins, and stores only sanitized local execution history.

**Tech Stack:** Chrome Manifest V3, vanilla JavaScript/HTML/CSS, Node.js built-in test runner (`node:test` + `assert`), JSON Schema, GitHub raw content as read-only command bus.

**Spec:** `docs/superpowers/specs/2026-09-14-google-flow-persistent-autopilot-design.md`

## Global Constraints

- No Google password, cookie, session token, 2FA code, GitHub PAT, OAuth refresh token, or other secret may be stored in source, queue payloads, logs, or status.
- Remote mode supports only bounded `render` commands; no generic JS, arbitrary clicks, arbitrary shell/file actions, or credential entry.
- Final manifest must not use `<all_urls>`.
- Allowlisted Flow origins are `https://flow.google.com/*` and `https://labs.google/fx/tools/flow/*`.
- Canonical command queue is `automation/google_flow/queue.json` on branch `automation/google-flow-command-bus`.
- Remote mode must fail closed on missing/ambiguous selector calibration, expired command, unsupported action/asset mode, login/CAPTCHA/quota/manual-attention state, or navigation outside the allowlist.
- A command must never be submitted twice solely because Chrome or the extension service worker restarted.
- Default retry ceiling is one attempt to avoid runaway Flow credit consumption.
- No completion claim without test evidence plus observable browser evidence for the Scene 24 E2E acceptance path.

---

### Task 1: Queue schema, validator, and RED tests

**Files:**
- Create: `automation/google_flow/schemas/queue.schema.json`
- Create: `automation/google_flow/chrome_extension/lib/queue.js`
- Create: `automation/google_flow/tests/queue.test.mjs`

**Interfaces:**
- Produces: `validateQueue(queue, nowMs) -> { ok:boolean, errors:string[], commands:NormalizedCommand[] }`
- Produces: `normalizeCommand(raw) -> NormalizedCommand`
- Produces: `isAllowedFlowUrl(url) -> boolean`

- [ ] **Step 1: Write failing tests**

Test valid queue, expired command rejection, unsupported action rejection, duplicate `command_id` rejection inside one queue, retry ceiling rejection, and origin allowlist behavior.

- [ ] **Step 2: Run RED**

Run: `node --test automation/google_flow/tests/queue.test.mjs`
Expected: FAIL because `lib/queue.js` does not exist.

- [ ] **Step 3: Implement minimal queue library and schema**

Use pure JavaScript with no external dependency so the same functions can execute in the extension and Node tests. Supported action is exactly `render`. Supported asset modes initially accepted by schema are `current`, `none`, `local_file`, and `remote_url`, while execution support is handled separately.

- [ ] **Step 4: Run GREEN**

Run: `node --test automation/google_flow/tests/queue.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(flow): add bounded render queue schema`

---

### Task 2: Command-state dedupe and persistence logic

**Files:**
- Create: `automation/google_flow/chrome_extension/lib/state.js`
- Create: `automation/google_flow/tests/state.test.mjs`

**Interfaces:**
- Produces: `shouldProcess(command, history, nowMs) -> { process:boolean, reason:string }`
- Produces: `markState(history, commandId, state, meta) -> history`
- Produces: `nextRunnableCommand(commands, history, nowMs) -> command|null`

- [ ] **Step 1: Write failing tests**

Cover restart dedupe, chronological ordering, `not_before`, expiration, completed/failed/blocked handling, and bounded local history trimming.

- [ ] **Step 2: Run RED**

Run: `node --test automation/google_flow/tests/state.test.mjs`
Expected: FAIL because `lib/state.js` does not exist.

- [ ] **Step 3: Implement minimal deterministic state library**

Keep history sanitized: command ID, scene, state, attempt count, timestamps, error code only.

- [ ] **Step 4: Run GREEN**

Run: `node --test automation/google_flow/tests/state.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(flow): add persistent command dedupe state`

---

### Task 3: Fail-closed calibrated DOM adapter

**Files:**
- Create: `automation/google_flow/chrome_extension/lib/dom_adapter.js`
- Create: `automation/google_flow/tests/dom_adapter.test.mjs`

**Interfaces:**
- Produces: `resolveCalibratedTarget(documentLike, calibration, kind) -> { ok:boolean, element?:any, errorCode?:string }`
- Produces: `preflightDom(documentLike, calibration) -> { ok:boolean, errors:string[] }`
- Produces: `detectBlockingState(documentLike) -> string|null`

- [ ] **Step 1: Write failing tests**

Use small fake document/element stubs to prove zero match fails, multiple matches fail, hidden/disabled Generate fails, one visible prompt + one visible enabled Generate passes, and login/CAPTCHA/quota keywords block execution.

- [ ] **Step 2: Run RED**

Run: `node --test automation/google_flow/tests/dom_adapter.test.mjs`
Expected: FAIL because adapter is absent.

- [ ] **Step 3: Implement minimal adapter**

Remote mode must not use bottom-right-button heuristics. Calibration uses stored CSS selectors plus optional expected text/aria metadata, and requires exactly one visible match.

- [ ] **Step 4: Run GREEN**

Run: `node --test automation/google_flow/tests/dom_adapter.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(flow): add fail-closed calibrated dom adapter`

---

### Task 4: Manifest V3 service worker, polling, alarms, and bounded navigation

**Files:**
- Create: `automation/google_flow/chrome_extension/manifest.json`
- Create: `automation/google_flow/chrome_extension/background.js`
- Create: `automation/google_flow/tests/manifest.test.mjs`

**Interfaces:**
- Consumes: queue/state helpers.
- Produces: service-worker messages `GET_CONFIG`, `SET_AUTOPILOT`, `POLL_NOW`, `GET_STATUS`, `OPEN_OR_FOCUS_FLOW`, `DOWNLOAD_URL`.

- [ ] **Step 1: Write failing manifest/security tests**

Assert manifest version 3, required permissions only, `alarms` present, no `<all_urls>`, and host permissions limited to the two Flow origins plus exact raw GitHub origin.

- [ ] **Step 2: Run RED**

Run: `node --test automation/google_flow/tests/manifest.test.mjs`
Expected: FAIL before manifest exists.

- [ ] **Step 3: Implement manifest and background worker**

Persist `autopilotEnabled`, `commandBusUrl`, polling interval, history, calibration, and current status. Register a coarse `chrome.alarms` poll. Fetch only configured canonical raw GitHub URL by default. Open/focus only allowlisted Flow URLs.

- [ ] **Step 4: Run GREEN**

Run: `node --test automation/google_flow/tests/manifest.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(flow): add persistent autopilot service worker`

---

### Task 5: Content executor for bounded render command

**Files:**
- Create: `automation/google_flow/chrome_extension/content.js`
- Create: `automation/google_flow/chrome_extension/lib/executor.js`
- Create: `automation/google_flow/tests/executor.test.mjs`

**Interfaces:**
- Produces: `preflightRender(command, pageContext, calibration) -> { ok:boolean, errors:string[] }`
- Produces: `executeRenderCurrent(command, targets) -> Promise<{submitted:boolean}>`

- [ ] **Step 1: Write failing tests**

Cover `start_image.mode=current` success, `end_image.mode=none`, unsupported `local_file`/`remote_url` execution failing closed until separately enabled, prompt fill, exactly one Generate click, and no click when preflight fails.

- [ ] **Step 2: Run RED**

Run: `node --test automation/google_flow/tests/executor.test.mjs`
Expected: FAIL because executor is absent.

- [ ] **Step 3: Implement minimal executor**

For v0.3 acceptance, fully support `current` + `none`. Fill prompt through native input/contenteditable events, then click the unique calibrated Generate control exactly once. Set local state to `submitted` and then `waiting`; never mark `completed` solely from the click.

- [ ] **Step 4: Run GREEN**

Run: `node --test automation/google_flow/tests/executor.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(flow): execute calibrated current-image renders`

---

### Task 6: Extension panel, calibration UX, persistence controls

**Files:**
- Create: `automation/google_flow/chrome_extension/popup.html`
- Create: `automation/google_flow/chrome_extension/popup.css`
- Create: `automation/google_flow/chrome_extension/popup.js`
- Create: `automation/google_flow/chrome_extension/panel.css`

**Interfaces:**
- Consumes background messages and local status.
- Produces user controls: Autopilot ON/OFF, command bus URL, interval, Run preflight, calibration selector fields, Pause/Resume/Stop, current/last command, local log export.

- [ ] **Step 1: Implement UI with safe defaults**

Autopilot defaults OFF on first install. Canonical command URL is prefilled. Calibration status must be explicit for prompt and Generate before remote execution can submit.

- [ ] **Step 2: Add persistence wiring**

Autopilot preference, URL, interval, and calibration persist in `chrome.storage.local` across browser restarts.

- [ ] **Step 3: Verify syntax**

Run `node --check` on JavaScript files.

- [ ] **Step 4: Commit**

Commit message: `feat(flow): add persistent autopilot control panel`

---

### Task 7: Canonical docs, cross-chat handoff, and command-bus branch

**Files:**
- Create: `automation/google_flow/README.md`
- Create: `automation/google_flow/CURRENT_HANDOFF.md`
- Create on branch `automation/google-flow-command-bus`: `automation/google_flow/queue.json`

**Interfaces:**
- `CURRENT_HANDOFF.md` gives future chats the exact command branch/path/raw URL and bounded write procedure.

- [ ] **Step 1: Create command-bus branch from current main**

Branch: `automation/google-flow-command-bus`.

- [ ] **Step 2: Create empty queue**

```json
{
  "schema_version": 1,
  "updated_at": "<ISO8601>",
  "commands": []
}
```

- [ ] **Step 3: Write operator README and cross-chat handoff**

Document installation, calibration, persistent Autopilot, queue append procedure, security boundaries, and the rule that future chats must not claim success without browser evidence.

- [ ] **Step 4: Commit**

Commit message: `docs(flow): document persistent autopilot command bus`

---

### Task 8: Full regression verification and extension package

**Files:**
- Create locally for user delivery: `google-flow-render-controller-v0.3.0.zip`
- No binary ZIP is committed to GitHub unless explicitly desired later.

**Interfaces:**
- Packaged folder root must contain `manifest.json` directly for Chrome `Load unpacked` after extraction.

- [ ] **Step 1: Run all unit tests**

Run: `node --test automation/google_flow/tests/*.test.mjs`
Expected: all PASS.

- [ ] **Step 2: Run syntax checks**

Run: `node --check` on all extension JS files.

- [ ] **Step 3: Static security verification**

Search manifest/source for `<all_urls>`, password/cookie/token collection, generic eval/Function execution, and unrestricted arbitrary navigation. Expected: none.

- [ ] **Step 4: Package ZIP**

Create `google-flow-render-controller-v0.3.0.zip` with extension source and operator README.

- [ ] **Step 5: Verify ZIP contents**

Confirm manifest version `0.3.0`, required files present, and no secrets.

- [ ] **Step 6: Commit final source/doc updates**

Commit message: `test(flow): verify persistent autopilot v0.3`

---

### Task 9: Scene 24 live acceptance preparation

**Files:**
- Update on command-bus branch: `automation/google_flow/queue.json`

**Interfaces:**
- Enqueue one bounded command using `start_image.mode=current`, `end_image.mode=none`, duration 8, aspect 16:9, and the approved Scene 24 prompt.

- [ ] **Step 1: Confirm extension is installed/reloaded and calibrated on current Flow UI**

This step requires the user's local Chrome and cannot be inferred from repository state.

- [ ] **Step 2: Run local preflight**

Expected: allowlisted origin, one prompt target, one enabled Generate target, current start image present, no blocking login/CAPTCHA/quota state.

- [ ] **Step 3: Append Scene 24 command**

Use a unique `command_id` and one-attempt retry ceiling.

- [ ] **Step 4: Observe browser evidence**

Success evidence is Flow visibly entering generation/render state or exposing a resulting video/download control. If unavailable, report exact blocker instead of success.
