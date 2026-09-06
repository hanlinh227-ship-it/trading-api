# AI WRITE LOCK

LOCKED: true
SCOPE: Bybit Auto production quality/runtime + protected trading authority
UPDATED: 2026-08-27

GitHub `main` is authoritative. Current Bybit Auto production design is **BYBIT-AUTO-1.9.1**. Signal V11 is historical/research-only unless explicitly referenced by current source.

## Hard production invariants
Preserve:
- existing `TRADING_STATE` KV and learning history without reset;
- Cloudflare native Bybit Auto scheduler and private authenticated Bybit transport;
- fresh quote + bounded re-anchor + structural SL/TP + deterministic liquidity/spread/chase gates;
- Continuous Equity-Curve Full-Capital Allocator: risk is a ceiling, not a forced spend;
- `maxOpenPositions: 1_000_000` (unlimited sentinel; actual entry authority is portfolio risk/margin/correlation/exchange gates);
- `maxSameDirectionPositions: 1_000_000` (unlimited sentinel; correlation and portfolio gates remain authoritative);
- `maxMarginPerPositionPct: 100`, with equity-aware slot decay sizing; `PORTFOLIO_MARGIN_HEADROOM` enforces runtime headroom;
- `minFreeReservePct: 0`; reserve is enforced dynamically by portfolio headroom rather than a fixed config floor;
- `targetRiskPctOfEquity: 6%` and `maxRiskPctOfEquity: 6.5%`, with the effective per-trade target declining as equity scales up;
- `maxTotalOpenRiskPct: 36%` hard portfolio risk ceiling;
- adaptive threshold hard bounded to `66–84`;
- correlation/beta gate for same-direction live exposure with `0.86` soft / `0.95` hard defaults;
- learning influence is zero below minimum sample and bounded afterward;
- per-symbol + strategy + regime memory may alter ranking/threshold only inside bounds;
- net expectancy after known costs is preferred over gross expectancy;
- adaptive exit selection limited to DEFENSIVE / BALANCED / TREND_RUNNER presets;
- adaptive/learning `autoPromote:false` permanently;
- strict fail-closed Claude + Codex final-entry authority; post-AI quote validation mandatory;
- structural anti-sweep SL geometry remains deterministic and cannot be weakened by learning;
- verified exchange-side TP/SL protection plus delayed BE / profit-lock / trailing management;
- native trailing floor remains 1.70R with 1.85R default trigger unless a stricter runtime value is supplied;
- Smart CUT canonical multi-signal invalidation, always `reduceOnly` for CUT;
- daily target OFF; 3-loss 30-minute new-entry pause; management continues during blocks;
- Telegram notifications/health must reflect runtime truth; learning remains backend state even when UI buttons are absent.

Never allow adaptive learning to lower freshness, SL geometry, RR, single-trade risk cap, total-open-risk cap, portfolio margin/headroom, max leverage or protection gates. Never let historical edge alone force an entry. Never close a legacy position merely to create capital headroom.

## Adaptive Edge invariant
Regime is deterministic and cannot be overridden by AI. Correlation failures are fail-closed in LIVE mode. Historical edge is confidence-weighted and cannot affect entries before the minimum sample guard. Candidate ranking can use bounded net expectancy, but all deterministic gates still own execution authority. No code path may set `autoPromote:true`.

## Smart CUT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`. Smart CUT is exceptional and requires confirmed thesis invalidation; slow trade, noisy M1, later scan or ordinary profit giveback alone are insufficient.

## Current profile — BYBIT-AUTO-1.9.1
- Scan cadence: 60s.
- Live universe minimum target: 80 symbols.
- Default minimum 24h turnover for universe: $750,000.
- Default scan concurrency: 12.
- Entry cooldown: 60s minimum.
- Score bounds: 66–84; current symbol profiles remain scalp-tuned within those bounds.
- `maxOpenPositions`: unlimited sentinel (`1_000_000`).
- `maxSameDirectionPositions`: unlimited sentinel (`1_000_000`).
- `maxMarginPerPositionPct`: 100% config ceiling with slot-margin decay curve.
- `maxPortfolioMarginPct`: 100% portfolio allocation ceiling.
- `minFreeReservePct`: 0%; runtime headroom gate owns enforcement.
- Target risk: 6% equity curve; hard per-trade cap: 6.5% equity.
- Total managed open risk hard cap: 36% equity.
- Correlation: soft 0.86 / hard 0.95.
- Minimum RR: 1.5; preferred RR: 1.8.
- Native trailing: hard floor 1.70R, default 1.85R.
- Daily target: OFF.

## Deployment
Production deploy path `.github/workflows/deploy-cloudflare-worker.yml`. Source validation + Cloudflare deploy + `/bybit/health` matching revision/version are mandatory before LIVE confirmation. Documentation-only commits must not be represented as production deploy evidence.

## Meme Alpha isolated writer — 2026-09-06

LOCKED: false
OWNER: CHATGPT
SCOPE: Meme Alpha only: source verification, safe-universe qualification, cost-aware rotation, held-position continuity, realized-capital sizing, regression tests and Meme checkpoint/handoff. No Bybit, signer/private-key or OS permission changes. Existing Bybit lock above is preserved.
AUTHORITY: User explicitly authorized taking over Meme Alpha after the lock ambiguity was reported.
STATUS: RELEASED — V386 pure policy and 33 tests committed on codex/meme-v386-cost-aware-policy; live strategy unchanged. Independent review and integration pending; see branch README. Bybit lock above remains unchanged.
