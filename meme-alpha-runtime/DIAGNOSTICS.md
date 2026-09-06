# Meme Alpha VPS Diagnostics

- UTC: 2026-09-06T03:52:49Z
- Runner user: github-runner
- Host: 59670.vpsvinahost.vn

## /opt/meme-alpha directories
```
/opt/meme-alpha
```

## /opt/meme-alpha files (names only; no contents)
```
```

## Meme-related system services
```
meme-alpha-micro-live.service                                     enabled         enabled
meme-alpha-paper.service                                          enabled         enabled
meme-alpha-realtime-pulse.service                                 enabled         enabled
meme-alpha-signer.service                                         enabled         enabled
meme-alpha-trend-pulse.service                                    enabled         enabled
meme-alpha-whale-flow.service                                     enabled         enabled
```

## Meme-related service runtime states
```
  meme-alpha-micro-live.service                                     loaded    active   running Meme Alpha MICRO_LIVE mirror executor v1.9.2
  meme-alpha-paper.service                                          loaded    active   running Meme Alpha Autonomous PAPER Engine
  meme-alpha-realtime-pulse.service                                 loaded    active   running Meme Alpha realtime pool pulse
  meme-alpha-signer.service                                         loaded    active   running Meme Alpha isolated Jupiter-only signer
  meme-alpha-trend-pulse.service                                    loaded    active   running Meme Alpha v2.9 Fast Trend Pulse
  meme-alpha-whale-flow.service                                     loaded    active   running Meme Alpha on-chain whale flow intelligence
```

## Service execution topology
```
[meme-alpha-paper.service]
ExecStart={ path=/opt/meme-alpha/app/run-paper.sh ; argv[]=/opt/meme-alpha/app/run-paper.sh ; ignore_errors=no ; start_time=[Sun 2026-09-06 03:08:15 UTC] ; stop_time=[n/a] ; pid=3206520 ; code=(null) ; status=0/0 }
WorkingDirectory=/opt/meme-alpha/app
User=meme-alpha
Group=meme-alpha
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-paper.service

[meme-alpha-micro-live.service]
ExecStart={ path=/usr/bin/node ; argv[]=/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js ; ignore_errors=no ; start_time=[Sat 2026-09-05 21:33:59 UTC] ; stop_time=[n/a] ; pid=2963470 ; code=(null) ; status=0/0 }
WorkingDirectory=
User=meme-alpha
Group=meme-alpha-signer-client
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-micro-live.service

[meme-alpha-realtime-pulse.service]
ExecStart={ path=/usr/bin/node ; argv[]=/usr/bin/node /opt/meme-alpha/app/src/realtime-pool-pulse.js ; ignore_errors=no ; start_time=[Sun 2026-09-06 02:29:35 UTC] ; stop_time=[n/a] ; pid=3167210 ; code=(null) ; status=0/0 }
WorkingDirectory=
User=meme-alpha
Group=meme-alpha
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-realtime-pulse.service

[meme-alpha-trend-pulse.service]
ExecStart={ path=/usr/bin/node ; argv[]=/usr/bin/node /opt/meme-alpha/app/src/trend-pulse.js ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }
WorkingDirectory=/opt/meme-alpha/app
User=meme-alpha
Group=meme-alpha
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-trend-pulse.service

[meme-alpha-whale-flow.service]
ExecStart={ path=/usr/bin/node ; argv[]=/usr/bin/node /opt/meme-alpha/app/src/whale-flow-intel.js ; ignore_errors=no ; start_time=[Sun 2026-09-06 00:23:14 UTC] ; stop_time=[n/a] ; pid=3076088 ; code=(null) ; status=0/0 }
WorkingDirectory=
User=meme-alpha
Group=meme-alpha
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-whale-flow.service

[meme-alpha-signer.service]
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }
WorkingDirectory=
User=meme-alpha-signer
Group=meme-alpha-signer-client
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/meme-alpha-signer.service

```

## User-level meme services
```
```
