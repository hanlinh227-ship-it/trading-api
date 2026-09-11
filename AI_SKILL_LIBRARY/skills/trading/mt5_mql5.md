# Skill: mt5_mql5

Covers MetaTrader 5, MetaEditor, MQL5 Expert Advisors, indicators, trade/account APIs, and EA debugging.

- Distinguish points, pips, tick size/value, contract size, volume step, margin mode, and symbol-specific execution settings.
- Treat balance, equity, free margin, margin level, realized PnL, and floating PnL as distinct quantities.
- Use broker/symbol metadata instead of hard-coded assumptions where possible.
- Make order ownership explicit with symbol/magic/comment filters.
- Guard duplicate entries, repeated modification, stale position state, invalid stops, volume normalization, and trade-result codes.
- Test strategy logic separately from broker/execution plumbing when possible.
- For news/shock handling, reduce or adapt risk rather than silently disabling safety protections.
