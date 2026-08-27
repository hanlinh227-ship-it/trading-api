# FOREX PARALLEL REPAIR PLAN — 2026-08-27

Base observed before split: 96b66a235f973c6ce7cf558df2b5fc7fedd737bc

## Ownership split

### ChatGPT branch
`chatgpt/forex-runtime-hardening-20260827`

Owns ONLY Cloudflare Forex runtime/readability fixes:
- `cloudflare-worker/forex-autonomous-mt5-bridge.js`
- directly related Forex validators if needed

Tasks:
- preserve `AI_ENTRY_COOLDOWN` instead of overwriting it with `PURE_AI_2AI_NOT_HEALTHY` when no council call is due
- remove stale hard-alternation user-facing text; canonical policy is FREE BUY/SELL with anti-bias streak cap 3
- keep all The5ers/risk/news/RR/2AI fail-closed safety unchanged

### Claude branch
`claude/mt5-vps-bootstrap-repair-20260827`

Owns ONLY MT5/VPS appliance files and directly related MT5 recovery/deploy workflows:
- `vps/mt5-forex/*`
- `.github/workflows/mt5-*.yml` and MT5 deploy/recovery workflow only when necessary

Observed blocker:
- EX5 exists
- service repeatedly starts in `BOOTSTRAP_AUTH`
- `MT5_FOREX_AUTH_STATE=BOOTSTRAP_REQUIRED`
- repeated `MT5_FOREX_TERMINAL_APPEAR=FAIL`
- exit 69 / UNAVAILABLE
- restart counter approximately 380
- bridge sidecar is alive

Branches must not edit each other's owned files.

## Merge gate
Both branches must validate independently. Final integration must rebase latest main, merge both branches, run Forex validators, deploy, then prove stable terminal heartbeat + EA 1.002 + LIVE tradeAllowed + 2AI health before declaring READY.
