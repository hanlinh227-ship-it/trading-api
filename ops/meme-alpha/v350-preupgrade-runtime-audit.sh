#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
echo '=== V350 PREUPGRADE RUNTIME AUDIT ==='
echo "HOST=$(hostname)"
echo "NODE=$(/usr/bin/node -v 2>/dev/null || true)"
echo '--- run-paper relevant commands ---'
grep -nE 'radar|trend|safe-signal|scanner|micro-live-gate|LIVE_SIGNAL_MAX_AGE_SEC|sleep ' "$APP/run-paper.sh" 2>/dev/null | tail -n 120 || true
echo '--- services ---'
for s in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-trend-pulse.service meme-alpha-trend-prime.service meme-alpha-signer.service; do
  echo "[$s] $(systemctl is-active "$s" 2>/dev/null || true)"
  systemctl cat "$s" 2>/dev/null | grep -E '^(ExecStart|EnvironmentFile|Environment|User|Group|SupplementaryGroups)=' | sed -E 's/(=.*(KEY|TOKEN|SECRET|PASSWORD|PRIVATE)[^=]*=).*/\1<redacted>/I' || true
done
echo '--- runtime source candidates ---'
find "$APP/src" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort | grep -Ei 'radar|trend|scanner|signal|gate|micro-live|holder|security|token' || true
echo '--- optional provider env names only ---'
for f in /etc/meme-alpha/*.env /etc/default/meme-alpha*; do
  [ -f "$f" ] || continue
  echo "FILE=$f"
  sed -nE 's/^([A-Za-z_][A-Za-z0-9_]*)=.*/\1/p' "$f" | sort -u | grep -Ei 'BIRDEYE|HELIUS|JITO|RPC|JUP|WS|WSS|LASER|YELLOWSTONE' || true
done
echo '--- state paths ---'
find /var/lib/meme-alpha/data -maxdepth 3 -type f -name '*.json' -o -name '*.jsonl' 2>/dev/null | grep -E 'micro-live|radar|trend|signal' | head -n 80 || true
echo V350_PREUPGRADE_AUDIT=PASS