# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771815_DUAL_HYRO_ACCOUNTS.md`
4. `V771814_PROP_PORTFOLIO_GUARD.md`
5. `V771813_MICROSTRUCTURE_AUDIT.md`
6. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
7. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Canonical source is V77.18.15.** Production entrypoint is `cloudflare-worker/index.js`. Signal core remains `engine-v77168.js`. PROP runtime remains modular and now includes `hyro-multi-account.js` + `hyro-multi-ui.js` around the existing Hyro modules. Cloudflare is deployment only.

Important V77.18.15 commits:
- `22d642d2` — isolated Account B KV/secrets scope.
- `fa33b832` — cross-account anti-mirror exclusion support in runtime.
- `73d2cc80` — two-account Telegram PROP hub.
- `79686fac` — dual-account hub + single orchestrated cron wired into index.
- `fee1229d` — V77.18.15 validator locks.
- `d2daeef4` — dual-account checkpoint.

## NON-NEGOTIABLE SEPARATION / STATE
SIGNAL, PROP/Hyro and PERSONAL remain completely independent.
Never route SIGNAL candidates/orders into PROP. Never route PROP into PERSONAL.
Never reset `TRADING_STATE`, Signal LIVE ORDERS, PROP execution/idempotency/notification/position-manager/portfolio/multi-account state, or PERSONAL state.

## DUAL HYRO ACCOUNT MODEL
### TK1 / Account A
Existing Hyro account is preserved exactly. It keeps all existing secrets and legacy KV keys. No migration/reset is allowed.

### TK2 / Account B
Uses isolated KV prefix `v771815:hyro:B:` and dedicated credentials:
- `HYRO_B_BYBIT_API_KEY`
- `HYRO_B_BYBIT_API_SECRET`
- optional later: `HYRO_B_BYBIT_LIVE_API_KEY`, `HYRO_B_BYBIT_LIVE_API_SECRET`
- `HYRO_B_BYBIT_MODE`
- `HYRO_B_AUTO_EXECUTION`

B AUTO defaults OFF unless explicitly set true. Missing B credentials cause B cron to skip, not fail TK1.

If B profile is not yet stored, configuration rules may be cloned from A only as a template. Orders, balance, execution state, day state, notifications, position manager and portfolio state are never cloned.

## TELEGRAM HUB
PROP now routes first to a two-account menu:
- `Tổng 2 TK`
- `TK1`
- `TK2`

Each account has independent Tổng quan / Vị thế / Risk / Kết nối / Quét / Auto controls. Summary shows equity, day P/L, active positions and AUTO state per account.

## ANTI-MIRROR / HYRO COMPLIANCE
Hyro support prohibited copy trading/account mirroring/coordinated multi-account execution. Therefore a durable global anti-mirror state `v771815:hyro:anti_mirror` records recent executions.
A symbol+side executed on one account is excluded from the other account for 6 hours. Do not remove/bypass this to increase trade frequency.

## CRON
One PROP orchestrator runs A then B once per minute. Never restore a second legacy A cron alongside it. TK2 is skipped safely while credentials are absent.

## PER-SYMBOL ENTRY / MICROSTRUCTURE
Every coin keeps a stable method/profile. Families remain symbol/family specific; do not restore generic scanner. PROP uses funding plus family-weighted Bybit OI, Long/Short ratio, orderbook imbalance/depth and spread.

## A/B/C ENTRY POLICY
- A: full-quality MARKET, normal dynamic A risk.
- B: near-market; minimum RR/risk/funding/HTF rules remain required. Quick Scan may execute B; regular AUTO may use B only with strong microstructure confirmation.
- C: LIMIT/WATCH; never force MARKET.
Funding block remains authoritative.

## PORTFOLIO GUARD PER ACCOUNT
Each account independently uses:
- maximum 3 active symbols total;
- maximum 2 same direction;
- maximum 1 same-direction symbol in the same crypto cluster;
- minimum 3 minutes between new entries;
- quality-first ranking, third slot optional.
Account scale-up changes risk sizing from live equity; it does not increase slot count.

## DYNAMIC CAPITAL / SCALE-UP
Current Bybit equity is the live capital authority for each account independently. `profile.accountSize` is legacy risk-ratio reference only.

## POSITION MANAGEMENT
Each account independently keeps TP1 ~40%, TP2 ~35%, runner ~25%, SL -> BE after TP1, SL -> TP1 + trailing after TP2, structural/native initial protection. TK1 keeps `v771811:hyro:manage:*`; TK2 sees the same module keys only through its B prefix.

## CLOUDFLARE CONTRACT
- Source of truth: GitHub.
- Same Worker: `trading-v77-scanner`.
- Same raw KV namespace/binding: `TRADING_STATE`.
- TK2 isolation is logical key prefixing inside the same durable namespace; do not create a replacement KV namespace.
- `keep_vars: true`; secrets/vars retained.
- Cron every minute.

## DEPLOYMENT GATE
Do NOT claim V77.18.15 production-active until validator/Cloudflare build is green and newest version is at 100% traffic.
After deploy verify TK1 state/equity unchanged, new 2-account buttons render, TK2 stays safely OFF without credentials, and Signal/PERSONAL state remains intact.
Only after dedicated B API identity/telemetry/risk/native SLTP checks pass may `HYRO_B_AUTO_EXECUTION=true` be enabled.

## FROZEN RULES
V73 prior, V74 freshness/data authority, V76 rejected-method exclusions, V77.18.11 per-symbol management, V77.18.13 microstructure, V77.18.14 portfolio guard and all durable state rules remain active unless explicitly superseded.

## NEW CHAT PROMPT
`Tiếp tục Trading từ GitHub mới nhất. BẮT BUỘC đọc CURRENT_HANDOFF.md trước. Canonical V77.18.15. SIGNAL/PROP/PERSONAL độc lập. PROP có 2 Hyro account: TK1 giữ nguyên legacy state/secrets; TK2 dùng prefix v771815:hyro:B: + HYRO_B_* secrets. HUB điều khiển Tổng 2 TK/TK1/TK2. Một cron orchestrator A→B. Mỗi account có per-symbol strategy + funding + microstructure + A/B/C + live-equity sizing + TP1/TP2/runner + portfolio guard. Cross-account anti-mirror 6h cùng symbol+side là bắt buộc. B AUTO mặc định OFF. Bảo toàn toàn bộ TRADING_STATE/LIVE ORDERS/state qua deploy.`
