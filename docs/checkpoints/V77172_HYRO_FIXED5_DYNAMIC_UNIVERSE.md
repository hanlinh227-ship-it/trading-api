# V77.17.2 HYRO FIXED 5% + DYNAMIC UNIVERSE

Canonical wrapper: cloudflare-worker/index.js
Preserved prior hub: cloudflare-worker/hub-v77171.js
Base engine remains: cloudflare-worker/engine-v77168.js

Locked policy:
- Hyro daily profit objective: +5% of configured initial account size.
- No Telegram control may change this target.
- Risk firewall has higher priority than profit target; the target may never override prop drawdown/max-loss protections.
- SL policy: native stop at structural invalidation; never widen risk after entry.
- TP policy: adaptive structure/liquidity targets; execution plan requires target RR >= 1.5 in Hyro overlay policy.
- Dynamic Hyro universe: Bybit linear USDT perpetual contracts currently Trading.
- Auto eligible pool: top liquid contracts with 24h turnover >= 10M USD, max 200 symbols.
- 5M-10M turnover = caution/review; below 5M = low-liquidity block by default.
- Hyro low-cap official exposure rule remains 5% initial balance; uncertain low-cap assets require review before execution.

No API secret is stored in Telegram or GitHub. Auto trade remains OFF until account/API telemetry and execution are connected.
