# V11 Backtest Supervisor (VPS)

This directory will host the autonomous per-symbol supervisor described in `docs/ai-coengineer/VPS_BACKTEST_SUPERVISOR_SPEC.md`.

Target runtime:
- `/opt/trading-api`
- systemd `v11-backtest-supervisor.service`
- localhost health `127.0.0.1:8791`
- persistent state `/var/lib/trading-v11/backtest-supervisor`

The supervisor is research/calibration infrastructure only. It cannot execute trades and cannot unlock Signal V11 Telegram. Global success remains fail-closed until every current catalog symbol independently satisfies the approved >=80.00% evidence gate at RR exactly 1:1 or 1:2.
