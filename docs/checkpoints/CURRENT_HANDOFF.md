# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-25 UTC+7

## READ FIRST
1. Fresh-read GitHub `main`.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read this file.
4. Read `docs/ai-coengineer/WRITE_LOCK.md`.
5. Inspect current Bybit AUTO source before changing production.

GitHub `main` outranks stale historical checkpoints.

## ACTIVE PRODUCTION AUTHORITY

The production Worker is **Bybit Auto Trade Hub only**.

Canonical production state:
- version: `BYBIT-AUTO-1.2.0`;
- execution: Bybit LIVE;
- Signal V11 runtime/scheduler on this Worker: disabled;
- Cloudflare native scheduler: enabled for Bybit Auto;
- private authenticated exchange transport: VPS Bybit proxy;
- AI core: Claude + Codex + DeepSeek, final-entry review only;
- Telegram: automatic AUTO entry/status notifications;
- state: existing `TRADING_STATE` KV preserved.

Do not resurrect or treat historical Signal V11, V77/V78/V10, Hyro/TK2 or retired debug workflows as current execution authority.

## CURRENT FREQUENCY / ENTRY POLICY

Profile: `BALANCED_FREQUENT`.

Current intent:
- scan every minute;
- entry spacing 180 seconds;
- global floor score 70;
- configured spread ceiling 9 bps, subject to stricter symbol-profile gates;
- configured chase ceiling 0.60 ATR, subject to stricter symbol-profile gates;
- one-shot adaptive fresh/re-anchor before AI;
- no infinite refresh/re-anchor loop;
- 3 AI only review a final candidate;
- post-AI quote gate remains mandatory.

## RISK / LEVERAGE / MARGIN

- risk ladder remains balance-based;
- starting ladder around $50 balance = $5 planned risk / $10 planned reward;
- max total open risk = 30% equity;
- max open positions = 3;
- max same-direction positions = 2;
- adaptive leverage is capped at 5x;
- margin-use budget = 80% equity;
- leverage and margin failures are fail-closed;
- do not increase leverage or weaken protection merely to create more trades.

## POSITION MANAGEMENT

Normal exit path:
`SL -> BE -> PROFIT_LOCK -> TRAILING -> TP/STOP`.

Discretionary CUT is **OFF by default**. The bot must not market-close because a trade is merely slow or because profit gives back. Manager stays active even while new entries are blocked by cooldown or loss-streak pause.

## PRODUCTION FILES

Primary files:
- `cloudflare-worker/index.js`
- `cloudflare-worker/bybit-auto-config.js`
- `cloudflare-worker/bybit-auto-controller.js`
- `cloudflare-worker/bybit-auto-v1.js`
- `cloudflare-worker/bybit-scalp-engine.js`
- `cloudflare-worker/bybit-position-manager.js`
- `cloudflare-worker/bybit-v5-client.js`
- `cloudflare-worker/bybit-learning-engine.js`
- `cloudflare-worker/bybit-auto-hub.js`

## DEPLOYMENT CONTRACT

Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.

A production claim is valid only when:
1. current `main` contains the intended source;
2. `npm run check` passes;
3. Cloudflare deploy succeeds;
4. `/bybit/health` reports the expected runtime revision;
5. mode/ack/scheduler/ready state is visible and valid.

## HYGIENE RULE

Remove or retire anything that can execute, write, dispatch, duplicate authority, contradict current thresholds or mislead future startup. Historical evidence may remain read-only, but it must be clearly non-authoritative.

## OWNER EXPERIENCE

Do not ask the owner to manually run GitHub/VPS/Cloudflare steps when available tools can perform or verify them. Desired flow:
`PROMPT -> INTERNAL WORK -> VALIDATION -> LIVE CONFIRMATION -> FINAL RESULT`.
