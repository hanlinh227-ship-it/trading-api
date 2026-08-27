# BYBIT AUTO 1.9.1 STATE

Date: 2026-08-27

Canonical Bybit release after 1.9.0 entry-path hardening.

- Production turnover floor 750,000 USD/24h is now honored (legacy 1,000,000 hard clamp removed).
- Scan concurrency default 12.
- Candidate fallback queue: top 5 by default, bounded 1-8.
- Candidate-specific rejects advance to the next qualified symbol.
- Systemic portfolio blockers and missing required AI quorum remain fail-closed for the whole cycle.
- Structural SL/TP, min RR 1.5, preferred RR 1.8, 6.5% single-trade hard cap, 36% total managed open risk, correlation gates, strict Claude+Codex 2/2, post-AI revalidation, Smart CUT and bounded learning remain unchanged.
- Active authority marker: EQUITY_CURVE_FULL_CAPITAL_V191.
- Legacy 3AI diagnostic filename retired; canonical diagnostic is 2AI.
