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
11. Source payload declares its own `_origin`/`_provenance` -> ignored; the server's stamp is the only provenance, because a source that can label itself live will.
12. Source answers with no datable field -> `UNVERIFIED`, never `HISTORICAL_EVIDENCE`: not knowing *when* something was true is a different failure from knowing it is old.
13. Origin value this server does not recognise -> `NOT_OBSERVED`, never a fall-through to the freshness branch.
14. Any non-GET/HEAD request -> `405 CONTROL_TOWER_IS_READ_ONLY`; the dashboard holds no authority over any runtime, model or task.
15. Canonical `acceptance.py` unreadable -> `/api/fabric` is `UNAVAILABLE` with zero rows; no partial matrix, no cached guess, and the UI renders no fabric values at all.
16. Acceptance gate absent (`NOT_OBSERVED`) -> stays `NOT_OBSERVED`; it is never rounded up to `PASS`, and `FULL_ACTIVE` is never more observed than the gates beneath it.
17. `FAILOVER_PROOF=SIMULATED_ONLY` -> rendered `UNVERIFIED`: selection logic ran, no traffic was served.
18. Provider telemetry names no model -> the Model Fleet row is `NOT_OBSERVED`; no static fleet table exists, because a hard-coded one would assert a Model Mesh fact.
19. `/api/status` unreachable from the browser -> the whole view renders the error, not the last rendered values.
20. A surface with no telemetry source at all (Learning Fabric) -> an explicit `NOT_OBSERVED` panel, never an empty chart awaiting invented data.
