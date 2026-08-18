# CLEAN TELEGRAM V77.6.2

Updated: 2026-08-18 UTC+7
Status: unified operator-UI cleanup for Forex + Crypto + Metal.

## Scope

This release does not hide runtime faults from diagnostics. It separates operator UI from engineering diagnostics.

Telegram now shows only:
- MARKET / LIMIT-FILLED / LIMIT-PENDING / WATCH books;
- scan/deep counts;
- compact data coverage;
- actionable deep outcomes such as MARKET, LIMIT, WATCH, NO_ENTRY or DATA_BLOCK.

Telegram no longer dumps raw `Broad lỗi` or `Deep lỗi` strings for Forex, Crypto or Metal.

Raw provider/broad/deep failures remain available in:
- `/run-now?group=forex|crypto|metal` diagnostics;
- Worker logs;
- KV `lastRun` state.

## Additional cleanup

- Runtime/menu/status/Cron operator labels normalized to V77.6.2.
- Shared `v775DiagnosticsText()` is used by all three market groups, so the clean-UI rule is applied consistently.
- Partial coverage is shown neutrally as `Coverage: X/Y symbol có dữ liệu dùng được` rather than exposing provider error text.
- `ERROR` deep rows stay internal; actionable non-error outcomes remain visible.

## Canonical safety

V73 remains frozen. V74 remains live-analysis/execution authority. V75 remains data layer. V76 R2 remains research-only. V77.6.2 is an operational/UI cleanup and does not grant legacy V77 scoring new authority.
