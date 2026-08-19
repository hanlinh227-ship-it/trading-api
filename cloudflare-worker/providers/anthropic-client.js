// V78-013 — shared Anthropic Messages API transport primitive.
// V78-015 safety follow-up — Claude API is PAUSED by default.
//
// The user explicitly requested that no Claude/Anthropic API calls be made
// for now. Therefore network access is fail-closed and requires an explicit
// CLAUDE_API_ENABLED=true environment flag to resume later.
//
// Explicitly NOT unified (per DECISION-004 and verified real differences):
//   - max_tokens policy: claude-reviewer.js clamps dynamically (500-2200,
//     env-overridable); dual-ai-intervention.js hardcodes 950. Each caller
//     resolves and passes its own maxTokens value.
//   - system/user prompt content: completely different prompts per
//     subsystem — callers build and pass their own.
//   - budget/accounting: claude-reviewer.js has a daily-limit+cooldown
//     budget system; dual-ai-intervention.js has none (uses a separate
//     lease-based single-writer arbiter instead). Neither is touched here.
//   - review-verdict schema parsing remains caller-owned.

export function isClaudeApiEnabled(env) {
  return String(env?.CLAUDE_API_ENABLED || "").trim().toLowerCase() === "true";
}

export async function anthropicMessagesRequest(env, {model, maxTokens, system, userContent}) {
  if (!isClaudeApiEnabled(env)) throw new Error("CLAUDE_API_DISABLED");
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01"
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      system,
      messages: [{role: "user", content: userContent}]
    })
  });
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error(`Anthropic ${r.status}: ${body?.error?.message || "request failed"}`);
  return body;
}

export function extractAnthropicText(body) {
  return (body?.content || []).filter(x => x?.type === "text").map(x => x.text).join("\n");
}
