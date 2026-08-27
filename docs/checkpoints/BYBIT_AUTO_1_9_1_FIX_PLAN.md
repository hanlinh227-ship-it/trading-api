# BYBIT AUTO 1.9.1 FIX PLAN

Date: 2026-08-27
Base audited: main @ 29df33aa69f7b5ff58ec5cd54270136980914af2

Scope: Bybit-only entry-path conflict cleanup and live hardening.

- Fix turnover floor precedence so production `BYBIT_MIN_TURNOVER_24H_USD=750000` is actually honored.
- Replace single `scan.best` entry starvation with bounded top-candidate fallback.
- Continue to the next candidate only for candidate-specific rejects; stop fail-closed on system/quorum/portfolio hard blockers.
- Preserve structural SL/TP, RR, risk caps, correlation, strict Claude+Codex 2/2, post-AI revalidation, learning bounds and protection.
- Remove active runtime/version marker conflicts and synchronize validator/deploy verification to BYBIT-AUTO-1.9.1.
