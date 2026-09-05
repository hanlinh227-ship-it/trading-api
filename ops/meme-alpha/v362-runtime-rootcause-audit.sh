#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
ARM=/etc/meme-alpha/micro-live-armed
WRAP=/usr/local/sbin/meme-alpha-safe-deploy

echo '=== V362 RUNTIME ROOTCAUSE AUDIT ==='
echo NOW_UTC=$(date -u +%FT%TZ)
echo '--- deploy wrapper ---'
ls -l "$WRAP" "$ARM" 2>&1 || true
stat -c '%n owner=%U group=%G mode=%a type=%F' "$WRAP" "$ARM" 2>&1 || true
readlink -f "$ARM" 2>&1 || true
namei -l "$ARM" 2>&1 || true
findmnt -T "$ARM" -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1 || true
grep -E '/etc/meme-alpha| /etc ' /proc/mounts 2>/dev/null || true
if [ -r "$WRAP" ]; then sed -n '1,220p' "$WRAP"; fi

echo '--- micro live unit security ---'
systemctl cat meme-alpha-micro-live.service 2>&1 || true
systemctl show meme-alpha-micro-live.service -p ReadOnlyPaths -p ReadWritePaths -p InaccessiblePaths -p ProtectSystem -p ProtectHome 2>&1 || true

echo '--- source-health related files ---'
find "$APP/runtime-status" -maxdepth 1 -type f \( -iname '*source*' -o -iname '*health*' -o -iname '*risk*' -o -iname '*signal*' -o -iname '*gate*' \) -printf '%f %s %TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null | sort || true
for f in "$APP/runtime-status/source-health.json" "$APP/runtime-status/risk.json" "$APP/runtime-status/risk-state.json" "$APP/runtime-status/signal-snapshot.json" "$APP/runtime-status/micro-live-gate.json"; do
  if [ -f "$f" ]; then echo "--- $(basename "$f") ---"; head -c 12000 "$f"; echo; fi
done

echo '--- recent scanner/paper errors ---'
for f in "$APP/runtime-status"/*.log; do
  [ -f "$f" ] || continue
  N=$(grep -Eic 'error|fail|429|timeout|degraded|stale' "$f" 2>/dev/null || true)
  if [ "$N" -gt 0 ]; then echo "### $(basename "$f") matches=$N"; grep -Ei 'error|fail|429|timeout|degraded|stale' "$f" | tail -n 25 || true; fi
done

echo '--- service state ---'
for s in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service meme-alpha-signer.service; do echo "$s=$(systemctl is-active "$s" || true)"; done

echo V362_RUNTIME_ROOTCAUSE_AUDIT=COMPLETE
