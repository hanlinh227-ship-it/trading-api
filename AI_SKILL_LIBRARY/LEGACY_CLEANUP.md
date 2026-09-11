# GITHUB_BRAIN_V2 Legacy Cleanup

Cleanup scope: remove superseded update/checkpoint snapshots from the working tree so agents do not load competing authority. Git history remains the archive.

## Canonical replacements kept

- Global AI authority: `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
- Global router: `AI_SKILL_LIBRARY/router.yaml`
- Trading authority: `docs/checkpoints/CURRENT_HANDOFF.md`
- Trading canonical strategy pointer: `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`
- Current BTC-only migration/research/supporting verification files remain available where they are still useful.
- Separate project checkpoints such as Vietlott, MT5 experiments, reward-hunter/Kaggriculture current state, and data-infrastructure state are not deleted merely because they are outside the current BTC trading authority; the router prevents them from being globally preloaded.

## Removed global/AI legacy

- `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` — superseded by V2; `GITHUB_BRAIN_V1` remains an activation alias in `checkpoint.json`.

## Removed root trading snapshots

- `BYBIT_UI_HANDOFF_V432.md`
- `CHAT_HANDOFF_TRADING.md`
- `V73_PROFILE_AUDIT.txt`
- `V77130_ISOLATED_CHECK.txt`
- `V77142_CORE_LIVE.txt`
- `V77151_FOREX_METAL.txt`
- `V77154_FOREX_LIVE.txt`
- `V77167_LIVE_ORDER_CHECKPOINT.md`

These were historical multi-market/update/audit snapshots and are superseded by the routed trading authority.

## Removed Kaggriculture version snapshots

Historical V3/V4/V5.x/reviewer snapshots under `CHECKPOINTS/` are removed while `CHECKPOINTS/KAGGRICULTURE_REWARD_SOLVER_CURRENT.md` is retained as the current named state for that separate project.

## Removed retired trading snapshots under `docs/checkpoints/`

The 2026-09-04 trading handoff explicitly retired the previous multi-coin Bybit, Forex, Meme, Signal V10/V11 and prior AI-council execution authority. Accordingly V2 removes the competing working-tree snapshots for:

- `MASTER_TRADING_STATE.md` (stale Bybit Auto 1.7.3 authority)
- Bybit Auto 1.8.x/1.9.x plans, state files and old handoffs
- old multi-market/market-entry/indicator execution snapshots
- retired Forex, indices/futures, metals and Meme state files
- TwelveData/Unified V77-era runtime and Telegram update snapshots
- Signal V10/V11 triggers, masters, locks and run snapshots
- V77/Hyro/prop multi-market update/reviewer/build snapshots that no longer define current production authority

## Explicitly not removed by this cleanup

- executable source/runtime/configuration files;
- `CURRENT_HANDOFF.md` and `BYBIT_BTC_STATEFLOW_2_1_20260904.md`;
- BTC-only migration/research files and latest production verification;
- MT5 experiment/checkpoint files, because MT5 remains a distinct routed skill/project surface and no single replacement authority was proven in this migration;
- `DATA_INFRA_STATE.md`, `BUILD_DIAGNOSTIC_LATEST.txt`, and `VIETLOTT_POWER655_MASTER_STATE.md`;
- `CHECKPOINTS/KAGGRICULTURE_REWARD_SOLVER_CURRENT.md`.

## Recovery

Any removed file can be recovered from Git history. A future project that needs historical material should link a specific historical commit or promote a new single `CURRENT_AUTHORITY`; it must not restore many competing snapshots to the global bootstrap path.
