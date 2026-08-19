// V78-011 — shared Telegram Bot API transport primitive.
// Extracted byte-for-byte HTTP-call+JSON-parse pattern common to
// index.js, hub-v77171.js, claude-telegram.js, system-health.js,
// release-notifier.js, dual-ai-intervention.js and claude-reviewer.js.
// Guard checks (TELEGRAM_BOT_TOKEN/CHAT_ID presence), error-throw vs
// boolean-return interpretation, and reply_markup/payload construction
// all remain in each caller — this primitive only does the raw fetch+parse.
// engine-v77168.js is intentionally EXCLUDED: its telegram() wraps fetch
// with fetchTimeout()/AbortController (6500ms), a genuine behavioral
// difference not present in the other 7. Deferred to a future issue
// alongside its Wave 5 (V78-054) decomposition.

export async function telegramApiRequest(env, method, payload) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload)
  });
  return await r.json();
}
