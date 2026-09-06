# Existing VPS Update Channel

## auto-futures-update.service
```ini
# /etc/systemd/system/auto-futures-update.service
[Unit]
Description=Auto Futures GitHub Production Updater
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/trading/trading-api
ExecStart=/opt/trading/trading-api/auto-futures-v1/runtime/watch_github.sh
TimeoutStartSec=300
```

## auto-futures-update.timer
```ini
# /etc/systemd/system/auto-futures-update.timer
[Unit]
Description=Check Auto Futures GitHub Updates Every 5 Minutes
[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
AccuracySec=10s
Persistent=false
Unit=auto-futures-update.service
[Install]
WantedBy=timers.target
```

## Service execution metadata
```
ExecStart={ path=/opt/trading/trading-api/auto-futures-v1/runtime/watch_github.sh ; argv[]=/opt/trading/trading-api/auto-futures-v1/runtime/watch_github.sh ; ignore_errors=no ; start_time=[Sun 2026-09-06 04:03:03 UTC] ; stop_time=[Sun 2026-09-06 04:03:04 UTC] ; pid=3242554 ; code=exited ; status=0 }
WorkingDirectory=/opt/trading/trading-api
User=root
Group=
FragmentPath=/etc/systemd/system/auto-futures-update.service
```
