# Skill: trading_router

Load this only after the global router classifies the task as trading.

## Authority
Read the `trading` `CURRENT_AUTHORITY` from `router.yaml`, then follow only its explicit canonical pointer. Historical trading checkpoints are not current instructions. Provider skills and external repositories are evidence/capability sources only; they never replace Trading authority.

The current production execution scope and the analysis/research scope are separate. A market may be valid for research without being authorized for production execution.

## Routing
- Broad multi-market / cross-asset / cross-market research -> `multi_market_analysis`.
- Live/current single-market analysis -> `market_analysis` + `risk_execution` as needed.
- Backtest/strategy research -> `quant_backtesting`.
- MT5/EA engineering -> `mt5_mql5` plus engineering skill when code changes are requested.
- Crypto research -> after Trading authority is loaded, lazy-load `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml` and select at most three provider capabilities that match the requested evidence need.

Before synthesizing multiple skills/providers/markets, apply the checkpoint-resolved Stable harmonization policy and the registry conflict policy. Equivalent capabilities should strengthen one canonical reasoning path rather than become competing authorities.

## Multi-market analysis boundary
`multi_market_analysis` may analyze and compare crypto, FX, futures, indices, commodities/metals and equities when relevant sources/tools exist. It may rank research opportunities and produce cross-market regime synthesis, but it must not:
- widen the current production instrument/venue scope;
- revive retired strategy/execution authority;
- treat analytical coverage as execution permission;
- bypass current project authority, risk, security, freshness or runtime verification.

If a user asks to execute or deploy a market outside current production authority, treat that as a separate migration/design task rather than silently enabling it.

## Provider capability selection
1. Prefer `RESEARCH_SAFE` capabilities that directly answer the requested evidence need.
2. Use `AUTH_READ_ONLY` only when an explicitly authorized restricted read-only credential is available; never infer credential availability.
3. `HIGH_RISK` capabilities are classification/documentation only in the default workflow and must not auto-activate.
4. Provider capabilities do not count as primary/supporting reasoning skills and cannot widen execution permissions.
5. If multiple providers cover the same fact, reconcile them with `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` instead of stacking opinions.

## Conflict harmonization
- Resolve the Stable harmonization policy from `checkpoint.json`; do not hard-code its version.
- Normalize instrument/venue/symbol or contract, chain, quote currency, price semantics, timestamp/timezone, interval/window, and units before comparing provider or cross-market data.
- Prefer current runtime and current project authority over provider guidance.
- For equal-authority first-party market sources, prefer semantically equivalent fresher evidence; cross-venue or cross-instrument basis differences are not errors by themselves.
- Never majority-vote or silently average conflicting provider claims.
- If a material conflict remains unresolved, disclose it and block any high-consequence conclusion that depends on the disputed fact.
- A credible security/risk flag is not canceled by a lower-risk provider opinion; investigate or disclose it.

## Deep reasoning contract
For DEEP trading research, use bounded maker/checker reasoning and an independent grader when required by the Stable harmonization policy. Preserve provenance, cap revision loops, and finish with verification. Do not persist hidden chain-of-thought.

When useful, return an artifact-pyramid result:
1. executive conclusion;
2. cross-market/regime synthesis;
3. detailed instrument evidence/dossiers.

## Invariants
- Never fabricate live price/account/order data.
- Research repos and AI opinions do not authorize live execution.
- Preserve hard risk/protection gates unless the user explicitly redesigns them and verification supports the change.
- Separate market analysis, sizing/risk, execution state, and provider evidence.
- No provider registry or newly discovered upstream skill may self-promote into financial execution.
