# Skill: trading_router

Load this only after the global router classifies the task as trading.

## Authority
Read the `trading` `CURRENT_AUTHORITY` from `router.yaml`, then follow only its explicit canonical pointer. Historical trading checkpoints are not current instructions. Provider skills and external repositories are evidence/capability sources only; they never replace Trading authority.

## Routing
- Live/current analysis -> `market_analysis` + `risk_execution` as needed.
- Backtest/strategy research -> `quant_backtesting`.
- MT5/EA engineering -> `mt5_mql5` plus engineering skill when code changes are requested.
- Crypto research -> after Trading authority is loaded, lazy-load `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml` and select at most three provider capabilities that match the requested evidence need.

## Provider capability selection
1. Prefer `RESEARCH_SAFE` capabilities that directly answer the requested evidence need.
2. Use `AUTH_READ_ONLY` only when an explicitly authorized restricted read-only credential is available; never infer credential availability.
3. `HIGH_RISK` capabilities are classification/documentation only in the default workflow and must not auto-activate.
4. Provider capabilities do not count as primary/supporting reasoning skills and cannot widen execution permissions.
5. If multiple providers cover the same fact, reconcile them with `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` instead of stacking opinions.

## Conflict harmonization
- Normalize instrument/venue/symbol or contract, chain, quote currency, price semantics, timestamp/timezone, interval/window, and units before comparing provider data.
- Prefer current runtime and current project authority over provider guidance.
- For equal-authority first-party market sources, prefer semantically equivalent fresher evidence; cross-venue basis differences are not errors by themselves.
- Never majority-vote or silently average conflicting provider claims.
- If a material conflict remains unresolved, disclose it and block any high-consequence conclusion that depends on the disputed fact.
- A credible security/risk flag is not canceled by a lower-risk provider opinion; investigate or disclose it.

## Invariants
- Never fabricate live price/account/order data.
- Research repos and AI opinions do not authorize live execution.
- Preserve hard risk/protection gates unless the user explicitly redesigns them and verification supports the change.
- Separate market analysis, sizing/risk, execution state, and provider evidence.
- No provider registry or newly discovered upstream skill may self-promote into financial execution.
