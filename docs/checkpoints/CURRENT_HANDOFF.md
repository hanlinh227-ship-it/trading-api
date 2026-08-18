# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

## READ FIRST
1. `V77180_AUTO_READY_CONSOLIDATED.md`
2. `MASTER_TRADING_STATE.md`
3. `V771811_PROP_PER_SYMBOL_MANAGEMENT.md`
4. `ENTRY_EXECUTION_V76.md` and relevant market checkpoints when needed.

## CURRENT CANONICAL
**Canonical Hyro runtime is V77.18.12.** Production entrypoint remains `cloudflare-worker/index.js`. Cloudflare is deployment only; do not maintain a second hand-edited Worker copy.

Latest important commits:
- `6b479cb9` — A/B/C per-symbol scan tiers.
- `a2657003` — dynamic equity-based Hyro risk sizing/caps.
- `b4f68ca4` — A/B quick scan + dynamic capital gates wired into runtime.
- `082b668e` — compact Telegram PROP UI + dynamic capital/risk display.

## NON-NEGOTIABLE SEPARATION
SIGNAL, PROP/Hyro and PERSONAL remain fully independent. Never route SIGNAL candidates/orders into PROP, never route PROP into PERSONAL, and never reset any existing LIVE ORDERS/state during deploy.

## HYRO ENVIRONMENT
Current account phase is CHALLENGE => force Bybit Demo Trading (`api-demo.bybit.com`) with `HYRO_BYBIT_API_KEY/SECRET`. FUNDED may use `HYRO_BYBIT_LIVE_API_KEY/SECRET` later. Auto reconnect remains request + cron based.

## V77.18.12 — A/B/C QUICK SCAN
PROP per-symbol strategies from V77.18.11 remain active.

Quick Scan now classifies deep-scan results:
- **A / MARKET_PLAN**: full-quality setup, normal risk multiplier 1.0.
- **B / NEAR_MARKET_PLAN**: near-market setup that still requires aligned HTF direction, valid structural SL, BTC context where required, acceptable funding and RR >= 1.5; execution risk multiplier is 0.5.
- **C / LIMIT_PLAN or WATCH**: do not force MARKET. LIMIT may be used by regular AUTO; WATCH remains wait-only.

Quick Scan may execute A or B only. Regular AUTO remains more conservative and evaluates A MARKET + C LIMIT; it does not automatically use B near-market entries.

Funding block remains authoritative and cannot be bypassed by B tier.

## DYNAMIC CAPITAL / SCALE-UP
Do not use `profile.accountSize` as the live capital authority for sizing.

Every telemetry cycle reads current Bybit account equity. `hyroDynamicRiskView(profile, telemetry)` derives current capital basis from live equity and scales internal risk controls automatically.

Legacy configured USD risk values are treated as ratios relative to the old configured account size, preserving the user's original risk proportions while allowing automatic scale-up/down:
- A+ entry risk ratio
- max single-loss ratio
- combined open-risk ratio
- daily hard-stop ratio
- funded notional/margin ratios

Risk A uses 100% of the dynamically scaled A-risk budget. Tier B uses 50% of that budget. If equity falls, budgets shrink automatically. If Hyro scales the account up, budgets/caps scale with the newly observed equity without manual account-size reconfiguration.

Daily target uses 5% of the day's detected starting-equity basis so normal intraday profit does not continuously move the target upward.

## TELEGRAM UI
PROP buttons are compact two-per-row where practical:
- Tổng quan | Vị thế
- Risk | Kết nối
- Quét nhanh | Auto
- Demo only: Order | Cycle
- Cấu hình | Menu

Dashboard/Risk/Connection panels now display `Vốn tự nhận` from current equity and dynamic risk values instead of relying on the old nominal account-size label.

Quick-scan result includes:
- capital detected
- broad/deep counts
- A/B/C counts
- up to three nearest setups with tier, symbol, side, RR and strategy

## PER-SYMBOL / FUNDING / POSITION MANAGEMENT STILL ACTIVE
Do not restore generic scanner. Each symbol keeps deterministic strategy profile/family. Funding-aware entry filter remains active. TP1/TP2/runner management remains 40% / 35% / 25%, SL -> BE after TP1, SL -> TP1 + trailing after TP2. Position manager state remains under `v771811:hyro:manage:*`.

## STATE CONTINUITY — NEVER DELETE / RESET
Preserve existing `TRADING_STATE` namespace and all current keys, including Signal LIVE ORDERS, PERSONAL state, Hyro profile/control/runtime/execution/day/idempotency/notification keys and `v771811:hyro:manage:*`.

Deploys are additive/non-destructive only. Never recreate KV to fix display or sizing.

## DEPLOYMENT GATE
Do not claim V77.18.12 active until Cloudflare build containing `082b668e` or newer is green at 100% traffic.

After deploy verify:
1. Telegram compact buttons render.
2. Connection shows telemetry CONNECTED and `Vốn tự nhận` matching current Challenge equity.
3. Risk screen shows dynamic A/B risk and caps.
4. Quick Scan reports A/B/C counts and preview.
5. Tier B order, if ever selected, records `riskMultiplier: 0.5` and lower USD risk than A.
6. Existing Signal/PROP/PERSONAL state remains intact.

## FROZEN RULES
V73 statistical prior, V74 freshness/data authority, V76 rejected-method exclusions, V77.18.11 per-symbol strategy/funding/position-management and all prior separation/state-continuity rules remain active unless explicitly superseded above.

## NEW CHAT PROMPT
`Tiếp tục toàn bộ dự án Trading từ GitHub mới nhất. BẮT BUỘC đọc CURRENT_HANDOFF.md trước. Canonical Hyro là V77.18.12. PROP mỗi symbol có strategy riêng, funding-aware, TP1/TP2/runner + BE/trailing. Quick Scan dùng A/B/C: A full risk, B near-market 50% risk, C limit/watch; regular AUTO vẫn bảo thủ A MARKET + C LIMIT. Account sizing/risk tự lấy live equity, tự scale khi Hyro scale-up, không phụ thuộc accountSize cố định. Telegram PROP dùng nút compact. SIGNAL/PROP/PERSONAL độc lập và toàn bộ TRADING_STATE/LIVE ORDERS/state phải được bảo toàn qua deploy.`
