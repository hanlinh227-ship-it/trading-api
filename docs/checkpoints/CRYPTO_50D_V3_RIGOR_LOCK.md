# CRYPTO 50D V3 RIGOR LOCK

## Goal
Research every usable symbol from the configured Breakout universe. Symbols without sufficient trustworthy market history may be excluded only with an explicit reason. Never change the denominator silently.

## Data integrity
- Historical source and contract type must be recorded per symbol.
- Reject duplicate/non-monotonic candles and detect missing 15m bars.
- No test window may cross a material unresolved data gap.
- Require >= 300 days usable history where the listing age permits; otherwise mark SHORT_HISTORY and apply stricter reporting.
- Cache manifests record first/last candle, row count, gap count and retrieval time.

## Execution realism
- Signal is computed only from fully closed bars.
- Entry is next-bar open; no same-bar signal fill.
- If SL and TP are both touched in one bar, SL wins (conservative ambiguity rule).
- Fees and slippage are charged separately and configurable.
- Funding is included when available for positions spanning funding timestamps; if unavailable the report flags FUNDING_NOT_MODELED.
- Position overlap is prohibited within a symbol unless the profile explicitly supports pyramiding (V3 default: disabled).
- Timeouts are exits at market, not zero-R placeholders.

## Research protocol
- Exactly RR 1:1 or 1:2.
- Random contiguous 50-day DEV windows are allowed for research.
- Claude + OpenAI + DeepSeek receive DEV evidence only and may propose a new symbol-specific strategy/profile after failure.
- AI cannot change target WR, minimum trades, costs, data, validation evidence or historical results.
- Profile version is immutable once evaluated on validation.

## Robust promotion gate
A lucky 50-day window is never enough.

A candidate must pass:
1. DEV qualification.
2. At least 3 distinct unseen 50-day validation windows from the reserved validation pool.
3. Aggregate validation WR >= 80%.
4. Worst validation-window WR >= configured floor (default 70%).
5. Minimum aggregate validation trades >= 60 and minimum 20 resolved trades/window.
6. Positive aggregate expectancy after costs.
7. Positive net R in every validation window.
8. No unresolved material data gaps.

Validation windows are selected before evaluation from deterministic seeds and cannot be resampled because a result failed.

## Robustness tests
Before LOCKED status, run:
- fee/slippage stress at 1.5x and 2.0x baseline costs;
- entry-delay stress of one additional 15m bar;
- parameter-neighborhood perturbation around the chosen profile;
- long-only and short-only attribution;
- trade concentration check so a tiny cluster of trades does not dominate expectancy.

A profile that collapses under small perturbations is OVERFIT_REJECTED even if headline WR is >=80%.

## Metrics
Persist per symbol/profile/window:
- trades/wins/losses/timeouts;
- gross/net WR;
- gross/net R and expectancy;
- profit factor;
- max drawdown in R;
- max consecutive losses;
- long/short attribution;
- MAE/MFE where computable;
- costs in R;
- window start/end and seed;
- data-quality manifest;
- AI lineage and profile hash.

## Reporting honesty
Every DEV and validation PASS/FAIL is append-only. Final reports include configured universe, usable universe, excluded symbols + reason, all locked symbols and unresolved symbols. Never report target achievement by hiding failures or unavailable symbols.
