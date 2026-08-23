# Control Center adversarial cases

These cases define fail-closed behavior for the standalone observability surface.

1. Source returns JSON `null` -> source becomes DEGRADED; server must stay up.
2. Source returns array/scalar JSON -> source becomes DEGRADED; server must stay up.
3. Source returns far-future timestamp -> success/active state must downgrade.
4. Cached source crosses stale threshold before next upstream refresh -> `/api/status` response must downgrade it without upstream fetch.
5. Pipeline object stage has missing/old/future timestamp -> success/active stage must become UNKNOWN.
6. Pipeline scalar stage is `PASS`, `ACCEPT`, `ONLINE`, `RUNNING`, `WAITING`, or `REVIEWING` -> must become UNKNOWN because no stage-local timestamp exists.
7. One source stalls after headers -> abort remains active through body parsing; other sources and server remain isolated.
8. Non-finite or > Node timer max refresh settings -> bounded safe interval, never 1 ms overflow.
9. Qwen/OpenRouter source malformed/offline -> only that card degrades; other AI cards continue.
10. `/api/status` must not trigger upstream fetches; it materializes current freshness from cache only.
