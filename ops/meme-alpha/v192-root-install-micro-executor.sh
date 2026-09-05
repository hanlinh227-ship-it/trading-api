#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC=$APP/ops/security/micro-live-executor-v192.js
DST=$APP/src/micro-live-executor.js
UNIT=/etc/systemd/system/meme-alpha-micro-live.service
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
[ -f "$SRC" ] || { echo ABORT_EXECUTOR_NOT_STAGED; exit 1; }
[ "$(systemctl show actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service -p User --value)" = github-runner ] || { echo ABORT_RUNNER_NOT_ISOLATED; exit 1; }
install -o meme-alpha -g meme-alpha-deploy -m 0664 "$SRC" "$DST"
install -d -o meme-alpha -g meme-alpha -m 0700 /var/lib/meme-alpha/data/micro-live
install -d -o root -g meme-alpha-signer-client -m 0750 /etc/meme-alpha
cat > /etc/meme-alpha/micro-live-policy.json <<'JSON'
{"maxEntryLamports":3000000,"minReserveLamports":20000000,"maxPriceImpactPct":1.25,"maxWalletLamports":100000000}
JSON
chown root:meme-alpha-signer-client /etc/meme-alpha/micro-live-policy.json
chmod 640 /etc/meme-alpha/micro-live-policy.json
cat > "$UNIT" <<'EOF'
[Unit]
Description=Meme Alpha MICRO_LIVE mirror executor v1.9.2
After=network-online.target meme-alpha-signer.service meme-alpha-paper.service
Requires=meme-alpha-signer.service
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha
Group=meme-alpha-signer-client
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
ReadOnlyPaths=/opt/meme-alpha/app /var/lib/meme-alpha/data/paper /etc/meme-alpha
ReadWritePaths=/var/lib/meme-alpha/data/micro-live /run/meme-alpha-signer
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl disable --now meme-alpha-micro-live.service 2>/dev/null || true
rm -f /etc/meme-alpha/execution-mode /etc/meme-alpha/micro-live-armed /etc/meme-alpha/signer-enabled
node --check "$DST"
sudo -u meme-alpha /usr/bin/node "$DST" --self-test
[ "$(systemctl is-enabled meme-alpha-micro-live.service 2>/dev/null || true)" != enabled ]
! systemctl is-active --quiet meme-alpha-micro-live.service
echo MICRO_EXECUTOR_VERSION=1.9.2
echo MAX_ENTRY_SOL=0.003
echo MIN_RESERVE_SOL=0.020
echo MICRO_EXECUTOR_ENABLED=FALSE
echo MICRO_EXECUTOR_ACTIVE=FALSE
echo LIVE_EXECUTION=FALSE
echo V192_MICRO_EXECUTOR_INSTALLED_DISABLED_PASS
