# V77.18.21 — PROMPT-DRIVEN AUTONOMY LAYER

## Operating contract
The user only needs to state the goal/prompt. ChatGPT is PRIMARY and should use connected tools to audit the repository, implement changes, validate syntax/build, preserve state, update checkpoint/version information when possible, and report only after the engineering pass is complete. Do not ask the user to perform technical steps that available connected tools can perform.

## Claude final reviewer
Claude remains REVIEW-ONLY and ADVISORY. `claude-reviewer.js` now reviews a broader context: Signal engine, HUB, Health Guardian, Hyro scanner/runtime/execution, microstructure, portfolio guard, position manager, HOLD/TIGHTEN/CUT, and release notifier.

Automatic Claude triggers:
1. release/final-system review when the reviewer release state is new;
2. new Health Guardian error signature;
3. daily system-tuning review roughly every 24h, subject to usage budget/cooldown;
4. manual HUB review when requested.

Claude must look for code/config conflicts, unreachable paths, duplicate gates, over-filtering, HUB simplification opportunities, and market-specific entry methods for Crypto/Forex/Metals/Futures. It must not recommend weakening hard news, freshness, execution-authority or risk gates merely to increase trade frequency.

## Safety / authority
ChatGPT remains the only engineering decision maker. Claude has no permission to trade, close positions, deploy, change secrets, override risk, or mutate production state outside its isolated reviewer KV keys.

Never reset `TRADING_STATE` or Signal LIVE ORDERS `v775:books`. Preserve PROP execution/runtime/idempotency/position-manager/review state.

## Reviewer state
- `v771821:claude:last`
- `v771821:claude:budget`
- `v771821:claude:release`
- `v771821:claude:error_sig`
- `v771821:claude:daily_system_audit`

Default limits remain bounded: daily review budget, cooldown, and max output token cap. Anthropic secret remains only in Cloudflare Secret.

## Practical workflow
User prompt -> ChatGPT audit/implementation -> syntax/build validation -> deploy pipeline -> Health Guardian -> Claude final review -> ChatGPT evaluates reviewer findings on the next engineering interaction. Claude findings never self-apply to production.
