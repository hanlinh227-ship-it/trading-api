# Skill: trading_router

Load this only after the global router classifies the task as trading.

## Authority
Read the `trading` `CURRENT_AUTHORITY` from `router.yaml`, then follow only its explicit canonical pointer. Historical trading checkpoints are not current instructions.

## Routing
- Live/current analysis -> `market_analysis` + `risk_execution` as needed.
- Backtest/strategy research -> `quant_backtesting`.
- MT5/EA engineering -> `mt5_mql5` plus engineering skill when code changes are requested.

## Invariants
- Never fabricate live price/account/order data.
- Research repos and AI opinions do not authorize live execution.
- Preserve hard risk/protection gates unless the user explicitly redesigns them and verification supports the change.
- Separate market analysis, sizing/risk, and execution state.
