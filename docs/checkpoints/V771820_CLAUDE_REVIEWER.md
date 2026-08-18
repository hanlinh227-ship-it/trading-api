# V77.18.20 — ChatGPT Primary + Claude Reviewer

## Canonical state

- Worker canonical version: `V77.18.20`.
- Release name: `Claude Reviewer Integration`.
- ChatGPT remains the PRIMARY engineer/decision maker.
- Claude is REVIEW-ONLY and has no authority to trade, close positions, deploy, alter secrets, or override hard risk controls.
- Single Hyro PROP account remains canonical; TK2/multi-account runtime stays removed.
- Existing Signal books, Hyro runtime, position manager, review state, and `TRADING_STATE` KV namespaces are preserved.

## Claude connection

- Cloudflare Secret required: `ANTHROPIC_API_KEY`.
- Default API model: `claude-sonnet-5`.
- Endpoint: Anthropic Messages API `/v1/messages`.
- Optional overrides:
  - `ANTHROPIC_REVIEW_MODEL`
  - `ANTHROPIC_REVIEW_MAX_TOKENS` (default 1200, bounded 400–2000)
  - `CLAUDE_REVIEW_DAILY_LIMIT` (default 4, bounded 1–20)
  - `CLAUDE_REVIEW_COOLDOWN_MIN` (default 45, bounded 5–720)

## Automatic review triggers

1. First cron after a new Worker version becomes active: one `RELEASE_REVIEW`.
2. New Health Guardian ERROR signature: one `HEALTH_INCIDENT_REVIEW`.
3. No trigger / same release / same incident: no Claude call.
4. Manual HUB button `🧠 Claude Reviewer → 🔎 Review ngay`: `MANUAL_HUB_REVIEW`, still bounded by daily review limit.

## Review context and privacy

Claude receives only:
- public GitHub main commit/diff metadata,
- truncated contents of selected critical public source files,
- sanitized System Health summary.

Claude does not receive Cloudflare environment variable values, API secrets, Telegram token, Bybit secrets, or raw secret bindings.

## Reviewer output

Compact JSON contract:
- `verdict`: PASS / WARN / FAIL
- `confidence`
- `summary`
- `findings`
- `tuning`
- `must_fix`

The output is advisory. No reviewer output is wired to execution or deployment authority.

## State keys

Reviewer-owned only:
- `v771820:claude:last`
- `v771820:claude:budget`
- `v771820:claude:release`
- `v771820:claude:error_sig`

## Worker routes

- `/claude/status`
- `/claude/review/latest`
- `/claude/review/run`

## Telegram HUB

Main HUB adds:
- `🧠 Claude Reviewer`

Reviewer menu:
- `🧠 Trạng thái`
- `🔎 Review ngay`
- `⬅️ Menu`

Status explicitly displays ChatGPT PRIMARY and no trade / close / deploy permissions.

## Health Guardian

Health Guardian checks whether `ANTHROPIC_API_KEY` is configured but does not call Anthropic merely for health checks, avoiding unnecessary API spend.

## Build verification

Final post-model-correction verification:
- V77.18.20 present: PASS
- stale `hyroMultiStatus`: absent
- Claude runtime wiring: PASS
- HUB Claude button: PASS
- Health Claude secret check: PASS
- default `claude-sonnet-5`: PASS
- non-default sampling parameter absent: PASS
- npm install: PASS / 0 vulnerabilities
- prepare Wrangler: PASS
- Wrangler dry-run: PASS
- `TRADING_STATE` binding preserved
- bundle approximately 605.59 KiB / gzip 90.61 KiB

See `docs/checkpoints/V771820_BUILD_VERIFY.txt`.

## Production activation rule

Source/build is considered ready only after the Cloudflare deployment carrying V77.18.20 receives production traffic. The first cron then acts as the real Anthropic connectivity/model self-test: Claude either returns PASS/WARN/FAIL to Telegram or a bounded reviewer ERROR without affecting trading runtime.
