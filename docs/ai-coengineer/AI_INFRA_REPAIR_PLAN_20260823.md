# AI Infrastructure Repair Plan — 2026-08-23

This plan exists only to unblock the current DeepSeek-owned three-AI engineering loop before resuming V11 optimization task #119.

Current observed blocker from Actions run 32590437675: the DeepSeek implementation stage reaches validation, then `node scripts/ai/ai-loop-selftest.mjs` reports 130 PASS / 13 FAIL. The failures are infrastructure/contract checks, including trusted base checkout, isolated CI selftest, bootstrap trust, stale-head guarding, explicit secret handling/least privilege, missing TESTING state, missing ADVERSARIAL_REVIEWER role, browser-independence wording, and no-live-state-on-main rule.

Repair order:
1. Make the AI orchestration workflows and contract satisfy the existing fail-closed selftest without weakening its checks.
2. Preserve one-writer concurrency, exact-SHA Codex + Claude review, and no autonomous production merge/deploy.
3. Add factual health/heartbeat diagnostics for the VPS/VPC Claude+Codex bridge where supported, without secrets.
4. Re-run the selftest and closed-loop smoke.
5. Only after infrastructure PASS, resume #119 for V11 signal quality, Telegram Hub UX, and read-only Control Center.

Architecture truth:
- DeepSeek is the sole implementation writer while WRITE_LOCK is active.
- Codex and Claude are independent reviewers/advisers bound to the exact implementation SHA.
- Normal V11 automatic signal operation is Cloudflare-native and must remain independent of VPS availability.
- VPS/VPC is auxiliary AI review infrastructure; do not claim all three AIs are resident processes inside VPS unless runtime evidence proves that topology.
- V11 remains SIGNAL_ONLY. Never promote LIMIT/WATCH/MARKET_PLAN into MARKET or weaken freshness/SL/RR/deterministic gates.
