# Google Flow Persistent Autopilot v0.3 — Design

## Status

Approved in chat on 2026-09-14 for implementation planning. This document is the written design authority for the v0.3 implementation and must be reviewed before code execution.

## Goal

Install a Chrome extension once, then allow later ChatGPT conversations to enqueue Google Flow render jobs through GitHub without TinyFish, Runway, a paid browser-control service, or a credential-bearing local server. When Chrome is running and the Google account remains signed in, the extension should discover new jobs, open the requested Flow project if needed, prepare inputs, enter the prompt, submit generation, and continue through queued jobs with fail-closed behavior.

## Non-goals

- Do not bypass CAPTCHA, Google login, 2FA, anti-bot controls, quota/credit limits, or any Google security control.
- Do not store Google passwords, cookies, session tokens, 2FA codes, GitHub PATs, OAuth refresh tokens, or other secrets in GitHub, extension source, local logs, or command payloads.
- Do not claim render success without observable evidence in the browser.
- Do not make Google Flow free; only the automation layer is local/free.
- Do not modify the GitHub Brain router/kernel or Trading runtime to implement this feature.

## Routing and authority

- GitHub Brain route: `engineering -> automation`.
- Primary skill: `automation`.
- Supporting skills when needed: `security`, `verification`.
- Repository authority remains `hanlinh227-ship-it/trading-api` on `main`; the command bus uses a dedicated non-production branch so render commands do not trigger normal `main` deployment workflows.

## Architecture

The system has three isolated parts.

### 1. Durable project authority on `main`

Canonical documentation and extension source live on `main` after review/merge:

- `automation/google_flow/README.md` — user/operator instructions.
- `automation/google_flow/CURRENT_HANDOFF.md` — concise cross-chat state and exact command-bus location.
- `automation/google_flow/schemas/queue.schema.json` — queue contract.
- `automation/google_flow/chrome_extension/` — unpacked Chrome extension source.
- `automation/google_flow/tests/` — deterministic unit tests for queue validation, dedupe, expiry, asset resolution metadata, and DOM-adapter safety decisions.

This is documentation/source authority only. It does not contain live credentials or Google session data.

### 2. Dedicated GitHub command-bus branch

Use branch:

`google-flow-command-bus`

Canonical queue path on that branch:

`automation/google_flow/queue.json`

Raw URL consumed by the extension:

`https://raw.githubusercontent.com/hanlinh227-ship-it/trading-api/google-flow-command-bus/automation/google_flow/queue.json`

The command-bus branch name intentionally contains no `/` so the raw GitHub URL is unambiguous. The branch is never merged for routine commands. This prevents every render request from mutating `main` or triggering normal `main` deployment workflows.

Later ChatGPT conversations may read the current queue, append a new job with a unique `command_id`, and update only this dedicated branch.

### 3. Local Chrome extension runtime

Manifest V3 extension responsibilities:

- persist configuration in `chrome.storage.local`;
- use `chrome.alarms` to wake periodically after browser restarts;
- use faster in-page polling while a Flow tab is open;
- open or focus the requested Google Flow URL in the existing Chrome profile;
- validate and deduplicate queue commands;
- refuse expired, malformed, unsupported, or already-completed commands;
- resolve permitted asset modes;
- operate only on explicitly calibrated or semantically unambiguous Flow controls;
- click Generate only after preflight checks pass;
- maintain local execution history and blocking-error state;
- optionally download completed video when a reliable Download control or video URL is observable.

## Supported Flow origins

The extension may operate only on allowlisted Google Flow origins, initially:

- `https://flow.google.com/*`
- `https://labs.google/fx/tools/flow/*`

If Google changes the canonical origin, a source update and verification are required. Wildcard access to arbitrary websites is not part of the final design.

## Command queue contract

Top-level queue shape:

```json
{
  "schema_version": 1,
  "updated_at": "2026-09-14T05:00:00Z",
  "commands": []
}
```

Each command:

```json
{
  "command_id": "flow-20260914-scene24-001",
  "created_at": "2026-09-14T05:00:00Z",
  "not_before": null,
  "expires_at": "2026-09-15T05:00:00Z",
  "action": "render",
  "project_url": "https://labs.google/fx/tools/flow/...",
  "scene": 24,
  "prompt": "...",
  "duration_seconds": 8,
  "aspect_ratio": "16:9",
  "start_image": {
    "mode": "current"
  },
  "end_image": {
    "mode": "none"
  },
  "output_filename": "Scene_24.mp4",
  "retry": {
    "max_attempts": 1
  }
}
```

### Supported actions

v0.3 supports one public action:

`render`

No generic JavaScript execution, arbitrary navigation, arbitrary clicks, shell commands, file deletion, credential entry, or unrestricted browser automation is allowed through the command schema.

### Asset modes

`start_image` and `end_image` use an explicit mode:

- `current` — use the image already present in the current Flow composition; no upload.
- `local_file` — load a relative filename from a user-approved local asset root. Requires persistent directory permission when available and re-authorization if Chrome revokes it.
- `remote_url` — fetch a public HTTPS image URL only from an allowlisted host and convert it to a browser `File` for upload.
- `none` — no asset for that slot.

The first implementation must fully support `current`. `local_file` and `remote_url` may be enabled only after their permission and selector paths are verified by tests/manual E2E; unsupported modes fail closed rather than silently degrading.

## Persistent operation

### Browser lifecycle

- `chrome.storage.local` stores configuration, selector calibration, last processed IDs, and local history.
- `chrome.alarms` provides coarse wakeups after browser restart/service-worker suspension.
- When a Flow page is actively open, the content script may poll more frequently for responsiveness.
- A command is never executed twice solely because Chrome restarted.

### Deduplication

The extension stores a bounded set of processed `command_id` values. A command whose ID is already in the processed set is skipped.

The queue may retain historical commands. The extension processes unseen, valid, non-expired commands in chronological order.

## DOM calibration and safety

Google Flow is a changing web application. v0.3 must not depend on a dangerous "click the last button in the bottom-right" heuristic for remote execution.

### Calibration

The extension provides one-time calibration controls for:

- prompt input;
- Generate/Submit button;
- start-image upload control when used;
- end-image upload control when used;
- Download control when used.

Calibration records stable selector metadata in local storage. The operator explicitly chooses the correct element during calibration.

### Remote preflight

Before clicking Generate, all must be true:

1. page origin is allowlisted;
2. command schema is valid;
3. command is not expired or already processed;
4. requested project URL matches an allowlisted Flow origin;
5. prompt target resolves to exactly one visible editable control;
6. Generate target resolves to exactly one visible enabled control;
7. requested asset state is satisfied;
8. no local blocking state indicates login/CAPTCHA/quota/manual-attention requirement.

Any ambiguity blocks execution and produces a local error. No fallback arbitrary click is allowed in Remote mode.

## Security model

### Permission ceiling

Manifest permissions are limited to what the feature needs:

- `storage`
- `tabs`
- `scripting`
- `downloads`
- `alarms`
- optionally `notifications` for local attention-required alerts

Host permissions are limited to the Google Flow origins and `https://raw.githubusercontent.com/*`. The extension itself additionally validates that the configured command URL exactly targets `hanlinh227-ship-it/trading-api`, branch `google-flow-command-bus`, path `automation/google_flow/queue.json` unless the local user explicitly changes the command source. No `<all_urls>` in the final manifest.

### Command-channel trust

The queue is public because the repository is public. Therefore:

- commands must contain no secret information;
- extension only accepts the exact configured owner/repository/branch/path by default;
- command schema exposes only bounded render fields;
- a malicious third party cannot mutate the owner repository without write access, but the extension still validates every command;
- changing the configured command-bus origin requires an explicit local user action.

### Google account security

The extension reuses the Chrome profile's normal signed-in session but never reads, exports, or serializes Google cookies or credentials.

## Failure states

The extension pauses and requires local attention when it detects or cannot rule out:

- Google login page;
- CAPTCHA or anti-bot challenge;
- quota/credit exhaustion;
- permission prompt that requires a user gesture;
- missing/ambiguous calibrated selector;
- requested image missing;
- unsupported command/action/asset mode;
- render timeout;
- unexpected navigation outside allowlisted origins.

Retry count is command-bounded. Default `max_attempts = 1` to prevent runaway credit usage.

## Observability

Local-only execution state includes:

- command ID;
- scene;
- received time;
- state: `queued | preflight | submitted | waiting | downloaded | completed | blocked | failed | skipped`;
- attempt count;
- sanitized error code;
- timestamps.

Do not log raw cookies, tokens, hidden page state, private browser history, or passwords.

Because v0.3 contains no GitHub credential in the extension, it cannot securely write status back to the repository. Cross-chat success verification therefore remains unavailable unless a later separately approved authenticated status channel is designed. The assistant must not claim remote render completion without user-visible or independently observable evidence.

## User experience

The extension panel exposes:

- Autopilot `OFF / ON`;
- command-bus URL, prefilled with the canonical raw GitHub URL;
- polling interval;
- current command and state;
- last completed command;
- calibration status for required controls;
- `Pause`, `Resume`, `Stop`;
- `Run preflight`;
- local log export;
- local asset-root authorization when enabled.

Autopilot defaults to `OFF` on first install. Once explicitly enabled, the preference persists across browser restarts.

## Cross-chat workflow

After v0.3 is installed and Autopilot is ON:

1. User asks in a later ChatGPT conversation: `render Scene 24 trên Flow`.
2. ChatGPT refreshes current repository context, reads `automation/google_flow/CURRENT_HANDOFF.md`, and routes the request to `engineering -> automation`.
3. ChatGPT reads the command-bus queue on branch `google-flow-command-bus`.
4. ChatGPT appends a validated, non-secret render command with a new `command_id`.
5. Local extension polls the queue and executes the command when Chrome is running and Flow is usable.
6. If execution is blocked, the extension shows a local attention-required state. ChatGPT does not invent completion status.

## Scene 24 acceptance test

The initial E2E acceptance test uses the already-added Scene 24 start image in Google Flow:

- command action: `render`;
- scene: `24`;
- `start_image.mode = current`;
- `end_image.mode = none`;
- duration: `8` seconds;
- aspect ratio: `16:9`;
- prompt: the approved friendship/teamwork animation prompt from the conversation;
- expected preflight: prompt + Generate controls uniquely resolve;
- expected execution: prompt is filled and Generate is clicked exactly once;
- expected safety: no upload, no login manipulation, no duplicate submission;
- success evidence: Flow visibly enters generation/render state or exposes the resulting video/download control.

## Verification requirements

Before claiming v0.3 implementation complete:

1. JSON schema validates representative valid and invalid queues.
2. Unit tests prove dedupe, expiry, unsupported-action rejection, retry ceiling, and allowed-origin checks.
3. Unit tests prove Remote mode never selects a control when zero or multiple calibrated matches exist.
4. Manifest contains no `<all_urls>` and no unnecessary credential-bearing permissions.
5. Node/JavaScript syntax checks pass.
6. Extension loads successfully as unpacked in Chrome.
7. Manual E2E preflight is run against the current Google Flow UI.
8. Scene 24 test demonstrates one Generate submission from a `current` start image, or the implementation is reported as blocked with exact observed reason.

## Rollback

- Extension: disable/remove v0.3 and reinstall the last known-good ZIP.
- Command bus: set queue to an empty `commands` array or turn local Autopilot OFF.
- Repository: feature branch can be abandoned without affecting `main`; the dedicated command branch is independent of production deployment authority.
