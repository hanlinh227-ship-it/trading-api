// V78-013 — shared Anthropic Messages API transport primitive.
// Extracted byte-identical HTTP-call+JSON-parse+text-extraction pattern
// common to claude-reviewer.js and dual-ai-intervention.js.
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
//   - review-verdict schema parsing: claude-reviewer.js uses
//     normalizeReview(parseClaudeJson(text)); dual-ai-intervention.js uses
//     its own parse(text) with a different field schema. Each caller keeps
//     its own parser; this module only extracts raw text from the response.
//
// This primitive only does: build request, fetch, parse JSON (never
// throwing on parse failure — resolves to null), and throw a
// caller-recognizable Error on non-2xx exactly as both callers already did.

export async function anthropicMessagesRequest(env, {model, maxTokens, system, userContent}) {
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
