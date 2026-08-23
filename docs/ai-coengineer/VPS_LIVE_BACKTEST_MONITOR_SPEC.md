# V11 VPS Live Backtest Monitor — 2s View

Status: DESIGN / READ-ONLY / FAIL-CLOSED

## Goal
Provide a direct VPS view of Signal V11 backtest execution with a UI refresh interval of 2 seconds so an operator can see which symbols are actively FETCHING/TRAINING/VALIDATING/OOS_TESTING without relying on GitHub Actions log latency.

The monitor is observational only. It must never modify strategy parameters, pass/fail gates, evidence, Telegram state, or production trading state.

## Architecture

### Producer
`v11-backtest-supervisor.service`

The supervisor remains the only producer of backtest state. Each worker emits lightweight progress snapshots atomically under:

- `/var/lib/trading-v11/backtest-supervisor/live.json`
- `/var/lib/trading-v11/backtest-supervisor/events.ndjson`
- `/var/lib/trading-v11/backtest-supervisor/results/<SYMBOL>.json`

### Read-only monitor
Separate service:

- systemd: `v11-backtest-monitor.service`
- bind: `127.0.0.1:8791`
- read-only access to supervisor state root
- no GitHub token, exchange key, AI key, Telegram token, or production secret

Keeping the monitor separate allows it to stay online and show `STALE` if the supervisor process dies.

## Browser endpoints

- `GET /` — live dashboard
- `GET /api/live` — current snapshot
- `GET /api/symbol/<SYMBOL>` — latest symbol state/result
- `GET /api/events?limit=200` — recent progress events
- `GET /health` — monitor + supervisor heartbeat status

No mutation endpoints are allowed.

## Refresh / heartbeat

Browser refreshes `/api/live` every 2000 ms.

Supervisor heartbeat target: <=2 seconds while active.

Monitor health classification:

- `LIVE`: heartbeat age <=4 seconds
- `DEGRADED`: heartbeat age >4 and <=10 seconds
- `STALE`: heartbeat age >10 seconds
- `OFFLINE`: live state missing/unreadable

The page timestamp must come from VPS state, not from browser animation, so a frozen producer cannot look alive.

## Atomic state writes

Supervisor writes `live.json.tmp`, fsyncs, then atomically replaces `live.json` with `os.replace()`.

The monitor must never read a partially-written JSON document.

`events.ndjson` is append-only and rotated/capped to prevent unbounded disk growth.

## Live snapshot schema

Example shape:

```json
{
  "version": "V11-VPS-LIVE-1",
  "runId": "v11-20260823-221500",
  "mainSha": "<sha>",
  "heartbeatAt": "2026-08-23T15:15:02Z",
  "state": "RUNNING",
  "totalSymbols": 95,
  "queue": {
    "pending": 91,
    "active": 4,
    "completed": 0,
    "blocked": 0
  },
  "workers": [
    {
      "worker": 1,
      "symbol": "EURUSD",
      "market": "forex",
      "stage": "OOS_TEST",
      "stageProgressPct": 64.2,
      "fold": "3/5",
      "bars": 5520,
      "candidate": "frozen",
      "elapsedSec": 48.1,
      "updatedAt": "2026-08-23T15:15:02Z"
    }
  ],
  "lastCompleted": null
}
```

Values above are schema examples only, not evidence or current results.

## Per-symbol stages

Canonical progress stages:

1. `QUEUED`
2. `FETCHING_DATA`
3. `DATA_READY`
4. `BUILDING_FEATURES`
5. `TRAINING`
6. `VALIDATING`
7. `CANDIDATE_FROZEN`
8. `OOS_TEST`
9. `PASS`
10. `OOS_FAIL`
11. `NEEDS_RESEARCH`
12. `BLOCKED_DATA`
13. `ERROR`

No stage may be displayed as PASS unless the canonical deterministic backtest gate says PASS.

## Dashboard layout

Header:

- V11 BACKTEST LIVE
- LIVE/DEGRADED/STALE/OFFLINE badge
- current main SHA
- run ID
- VPS heartbeat age
- active workers / total workers

Active workers table:

- worker slot
- symbol
- market
- stage
- stage progress
- current fold/window
- bars loaded
- elapsed time
- last update

Queue table:

- symbol
- state
- retry/research generation
- last completed stage

Recent event console:

```text
22:15:00 [W1] EURUSD FETCHING_DATA
22:15:01 [W1] EURUSD DATA_READY bars=5520
22:15:02 [W1] EURUSD BUILDING_FEATURES
22:15:04 [W1] EURUSD TRAINING fold=1/5
22:15:07 [W2] BTCUSDT OOS_TEST
```

Events are observational; the assistant's user-reporting rule can remain silent until the global target is reached.

## UI behavior

JavaScript polling interval:

```js
const REFRESH_MS = 2000;
setInterval(loadLiveState, REFRESH_MS);
```

Each refresh updates only changed DOM rows to avoid page flicker.

Use an obvious stale banner when heartbeat does not move. Do not animate fake progress between server updates.

## Terminal view

A zero-dependency terminal option should also be supported:

```bash
watch -n 2 'curl -fsS http://127.0.0.1:8791/api/live | jq'
```

A dedicated compact TUI may later render the same endpoint, but it must remain read-only.

## Secure remote access

Default port remains localhost-only. Do not expose `8791` directly to the internet.

From a computer, use SSH local forwarding:

```bash
ssh -L 8791:127.0.0.1:8791 <user>@<vps>
```

Then open:

`http://127.0.0.1:8791`

For phone/browser access without SSH, prefer Cloudflare Tunnel + Cloudflare Access authentication in front of the localhost service. Never make the monitor a public unauthenticated endpoint.

## Resource design

- Dashboard poll: every 2 seconds
- `live.json`: small snapshot, target <100 KB
- no Git commits per heartbeat
- no market-data redownload caused by monitoring
- no AI calls caused by monitoring
- no strategy evaluation caused by page refresh

The monitor only reads already-produced local state, therefore the 2-second UI cadence should add negligible load to the actual backtest.

## Required implementation files

Recommended new files:

- `scripts/v11_vps_live_state.py` — atomic progress emitter/helper
- `scripts/v11_vps_live_monitor.py` — read-only HTTP server
- `signal-v11-vps/systemd/v11-backtest-monitor.service` — monitor systemd unit
- `signal-v11-vps/web/backtest-live/index.html` — dashboard UI

Required supervisor integration:

- emit heartbeat <=2 seconds while RUNNING
- emit stage transition for every active worker/symbol
- emit current fold/progress without changing deterministic engine semantics
- flush final symbol state before worker releases its slot

## Acceptance criteria

1. Browser reflects a supervisor state change within <=2.5 seconds under normal localhost conditions.
2. Multiple concurrent workers/symbols are visible independently.
3. Killing the supervisor causes dashboard to show STALE within <=10 seconds.
4. Restarting supervisor resumes display from persisted state.
5. Monitor has no write capability to strategy/evidence/production files.
6. Monitor does not alter backtest outputs when enabled versus disabled.
7. No secret values appear in HTML, API responses, logs, or state JSON.
8. PASS remains controlled only by canonical V11 deterministic evidence gates.
