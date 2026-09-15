# Model Mesh — Production Verification Record

**Status:** `KNOWN_GOOD = YES` for Brain release 4.9.1.

Every mandatory production contract passed on the exact-SHA gated deployment
run. Evidence below is quoted from that run, not from local tests.

## Verified revision

| Field | Value |
|---|---|
| Production live revision | `7db95e6d8c5c767125d180120afef56ce0a57fbe` |
| `main` HEAD at verification | `7db95e6d8c5c767125d180120afef56ce0a57fbe` |
| Deploy run | [34986670782](https://github.com/hanlinh227-ship-it/trading-api/actions/runs/34986670782) |
| Rollback target captured | `a4a9e96efa845e10f2eed0721f04b0728baae078` |
| Deployment authority | `deploy-skill-mandatory-fast-gateway.yml` (sole) |

## Mandatory contracts

```
RUNTIME_REVISION=PASS 7db95e6d8c5c767125d180120afef56ce0a57fbe
BRAIN_HEALTH=PASS 7db95e6d8c5c767125d180120afef56ce0a57fbe
MODEL_MESH_HEALTH=PASS 7db95e6d... configured=6 active=0   (pre-probe)
FINAL_EXACT_SHA_GATE=PASS revision=7db95e6d8c5c767125d180120afef56ce0a57fbe
PRODUCTION_LIVE_REVISION=7db95e6d8c5c767125d180120afef56ce0a57fbe
SKILL_MANDATORY_FAST_GATEWAY_DEPLOY=PASS
MODEL_MESH_MODE=FREE_ONLY
MODEL_MESH_MAX_PARALLEL=STANDARD=2 DEEP=4 FAST=0
PROVIDER_SECRET_SYNC=ELIGIBLE_PROVIDERS_ONLY
```

### Brain authority boundaries, proven against the running Worker

```
SECRET_EXTERNAL_BOUNDARY=PASS external_workers=0 http=403
DATACLASS_FAIL_CLOSED=PASS unknown_class_treated_as_secret http=403
FAST_EXTERNAL_BOUNDARY=PASS external_workers=0 externalRoutingCalls=0
BRAIN_ROUTE=PASS core_reasoning FAST 0ms
BRAIN_ROUTE=PASS debugging STANDARD 0ms
BRAIN_ROUTE=PASS advertising_copy FAST 0ms
BRAIN_ROUTE=PASS trading_router DEEP 0ms
```

### Planner

```
MODEL_MESH_PLAN=PASS STANDARD workers=0 reason=no_live_healthy_provider
MODEL_MESH_PLAN=PASS DEEP     workers=0 reason=no_live_healthy_provider
MODEL_MESH_POST_PROBE_PLAN=PASS STANDARD workers=2
MODEL_MESH_POST_PROBE_PLAN=PASS DEEP     workers=3
```

The first two lines are the all-providers-down contract observed in production
rather than simulated: a new `source_sha` invalidates prior evidence, so the
planner genuinely had no live provider and returned a correct graceful-zero
plan with `ok:true` instead of failing.

### Provider matrix (actual, not target)

```
MODEL_MESH_PROBE=PASS probed=5 configured=5 successful=3 unavailable=2
MODEL_MESH_LIVE_OVERLAY=PASS active=3
```

| Provider | Model | Status | State | Latency |
|---|---|---|---|---|
| `groq` | `openai/gpt-oss-120b` | 200 | LIVE_HEALTHY | 319 ms |
| `openrouter` | `openrouter/free` | 200 | LIVE_HEALTHY | 1 009 ms |
| `cloudflare_workers_ai` | `@cf/zai-org/glm-4.7-flash` | 200 | LIVE_HEALTHY | 2 311 ms |
| `gemini_developer_api` | `gemini-2.5-flash` | 404 | QUARANTINED | 184 ms |
| `mistral` | `mistral-small-latest` | 429 | COOLDOWN | 232 ms |

ACTIVE = 3. This is the truth, not a target. A provider counts as ACTIVE only
when it is FREE_ONLY eligible, configured, and carries fresh `LIVE_HEALTHY`
evidence. `opencode_zen` is deliberately not probed: it is
`usage_terms: evaluation`, so it is not production capacity and the canonical
policy's `usage_terms` filter excludes it.

### Evidence lane (OPTIONAL)

```
TINYFISH_HEALTH=PASS optional=true configured=true admissionControl=true
EVIDENCE_CANARY=PASS operation=search status=200 evidence=7 guardPersisted=true
EVIDENCE_CANARY=PASS operation=fetch  status=200 evidence=1 guardPersisted=true
TINYFISH_CANARY=success (optional, non-gating)
```

## Unresolved limitations

These do not block `KNOWN_GOOD` — no mandatory contract depends on them — but
they are real and must not be forgotten.

1. **`gemini_developer_api` returns 404 and is quarantined. Root cause open.**
   `GEMINI_MODEL_AVAILABILITY=PASS configured=gemini-2.5-flash` proves the
   configured model id IS present in the live `v1beta` listing, so this is NOT
   a registry typo and editing the registry would mask the real cause rather
   than fix it. The cause must be sought in the request shape or entitlement.
   The mesh degrades correctly around it.

2. **`mistral` is rate-limited at probe cadence.** Cooldown now follows the
   provider's own `Retry-After` and the provider is not re-probed while inside
   it, but the free tier may simply be too small for this cadence.

3. **The `*/10` refresh schedule has never fired.** Zero scheduled runs since
   the cron was added, against a 30-minute evidence TTL. The in-worker bounded
   `waitUntil` self-heal is therefore currently the ONLY working recovery path
   for stale evidence, not a redundancy. If the schedule starts working it
   becomes redundancy again; until then, do not remove the self-heal.

4. **Registry capability coverage is incomplete.** `domain_capabilities.yaml` is
   compiled in as ranking authority, but no admitted model declares
   `math_quant` or `data_analysis`, which the `trading` domain weights most
   heavily. Hard capability filtering is therefore NOT enabled -- a missing
   declaration ranks a model last rather than disqualifying it. Enabling hard
   filtering requires completing capability coverage first.

5. **KV has no compare-and-set.** Health writes are read-modify-write. The
   record stays well-formed under concurrent writes, but `consecutiveFailures`
   can under-count. Moving health state to a Durable Object is the fix if this
   ever becomes load-bearing beyond the quarantine threshold.
