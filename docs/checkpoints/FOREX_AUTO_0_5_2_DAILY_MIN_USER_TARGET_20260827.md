# FOREX AUTO 0.5.2 — DAILY MINIMUM + USER-SET TARGET LOCK

Updated: 2026-08-27 UTC+7
Status: canonical Forex requirement pending source/runtime alignment.

## USER REQUIREMENT
- Daily objective: finish each trading day above +0.5% realized/equity growth versus canonical broker day-start baseline.
- This is an objective, NOT permission to bypass risk, margin, news, execution-quality, freshness, RR, or broker/prop hard rules.
- The engine must never force a low-quality trade merely to chase +0.5%.
- If hard safety gates prevent further entries, the day may finish below +0.5%; this must be reported as DAILY_OBJECTIVE_MISSED rather than hidden or beautified.

## USER-SET CAMPAIGN TARGET
- No permanent fixed campaign target is allowed in source.
- Campaign target is OFF by default.
- A campaign target becomes active only when explicitly set by the user for that run/cycle.
- Target value and target horizon must be stored as runtime state/config, not hard-coded.
- Clearing the user target returns the engine to daily +0.5% objective mode only.
- User target may influence urgency/reporting but must never increase risk above canonical caps or weaken hard gates.

## AUTHORITY
- Forex branch remains independent from Bybit.
- Trading AI authority remains GPT/Codex + Claude 2/2.
- Broker/MT5 data remains execution authority.
- No DeepSeek/Qwen/OpenRouter fallback.

## VALIDATION
Source + tests + worker preflight + Forex validation workflow must be updated before declaring 0.5.2 canonical. LIVE promotion still requires explicit runtime enablement and health verification.
