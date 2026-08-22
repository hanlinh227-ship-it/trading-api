# AI Infrastructure Repair Execution Scope

Execution is intentionally limited to the AI orchestration layer needed to unblock the current three-AI closed loop. Trading logic is out of scope for this repair stage.

Allowed repair areas for the DeepSeek writer task: `.github/workflows/ai-loop*.yml`, `.github/workflows/ai-task.yml`, `scripts/ai/**`, and AI orchestration contract/docs under `docs/ai-coengineer/**`.

Forbidden during this stage: V11 market thresholds, freshness TTLs, SL/TP/RR logic, TRADING_STATE migration/reset, Binance execution authority, production Anthropic API enablement, or any change intended merely to increase signal count.

Completion gate: current AI-loop selftest must pass without removing or weakening assertions, then exact-SHA Codex and Claude reviews are required before merge consideration.
