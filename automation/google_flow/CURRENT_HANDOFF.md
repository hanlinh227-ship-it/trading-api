# Google Flow Autopilot — Current Handoff

## Current authority

- Feature: Google Flow Persistent Autopilot
- Target extension version: `0.3.0`
- Canonical source path after merge: `automation/google_flow/chrome_extension/`
- Design spec: `docs/superpowers/specs/2026-09-14-google-flow-persistent-autopilot-design.md`
- Implementation plan: `docs/superpowers/plans/2026-09-14-google-flow-persistent-autopilot-v0-3.md`

## Command bus

- Repo: `hanlinh227-ship-it/trading-api`
- Branch: `automation/google-flow-command-bus`
- Path: `automation/google_flow/queue.json`
- Raw URL: `https://raw.githubusercontent.com/hanlinh227-ship-it/trading-api/automation/google-flow-command-bus/automation/google_flow/queue.json`

Routine Flow commands must update only the command-bus branch, not `main`.

## Future-chat procedure

For a future request to render in Flow:

1. Refresh `AI_SKILL_LIBRARY/checkpoint.json` and current GitHub Brain authority.
2. Route to `engineering -> automation`.
3. Read this handoff.
4. Read `queue.json` from branch `automation/google-flow-command-bus`.
5. Append a new validated `render` command with unique `command_id`.
6. Never include password, cookie, session, token, 2FA, secret, or private credential in the queue.
7. Default `retry.max_attempts = 1`.
8. Do not claim success from GitHub write alone. Browser evidence is required.

## Execution support

v0.3 enabled execution:

- `start_image.mode = current | none`
- `end_image.mode = current | none`

`local_file` and `remote_url` are intentionally fail-closed until separately verified.

## Current acceptance target

Scene 24:

- Start image already present in Flow.
- `start_image.mode = current`
- `end_image.mode = none`
- duration 8s
- aspect 16:9
- prompt is the approved friendship/teamwork animation prompt from the chat.

## Verification boundary

The extension may submit a render when preflight passes. This repository does not currently have an authenticated status-return channel from local Chrome. Therefore future ChatGPT sessions must not say a video finished unless the user provides visible evidence or another independently verified status channel is later added.
