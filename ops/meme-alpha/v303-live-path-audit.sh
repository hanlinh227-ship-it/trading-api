#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V303 LIVE PATH AUDIT ==='
echo '=== MICRO LIVE / SIGNER SERVICES ==='
for s in meme-alpha-micro-live.service meme-alpha-signer.service; do
  systemctl is-active "$s" 2>/dev/null || true
  systemctl cat "$s" 2>/dev/null | sed -E 's/(Environment=.*(TOKEN|KEY|SECRET|PASSWORD|PRIVATE).*)/Environment=[REDACTED]/I' | head -180 || true
done

echo '=== LIVE FILE PERMISSIONS ==='
for f in src/micro-live-executor.js /etc/meme-alpha/micro-live-policy.json runtime-status/portfolio-shadow.json runtime-status/signal-snapshot.json runtime-status/trend-snapshot.json runtime-status/trend-pulse.json; do
  [ -e "$f" ] || continue
  stat -c '%n owner=%U group=%G mode=%a size=%s' "$f" || true
  [ -r "$f" ] && echo "$f READABLE=TRUE" || echo "$f READABLE=FALSE"
  [ -w "$f" ] && echo "$f WRITABLE=TRUE" || echo "$f WRITABLE=FALSE"
done

echo '=== LIVE EXECUTOR CONTROL FLOW ==='
if [ -r src/micro-live-executor.js ]; then
  nl -ba src/micro-live-executor.js | sed -n '1,320p' | sed -E 's/(token|secret|private[_-]?key|password)[[:space:]]*[:=][[:space:]]*[^,; ]+/\1=[REDACTED]/Ig'
fi

echo '=== SAFE LIVE STATE ==='
for f in runtime-status/portfolio-shadow.json runtime-status/signal-snapshot.json runtime-status/trend-snapshot.json runtime-status/trend-pulse.json; do
  [ -r "$f" ] || continue
  echo "--- $f"
  node - "$f" <<'NODE' 2>/dev/null || true
const fs=require('fs'); try {const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const keep=['version','timestamp','updatedAt','generatedAt','signalAgeSec','trendAgeSec','eligibleCount','shadowReady','liveExecution','reason','mode','maxPositions','maxSinglePositionPct','maxPortfolioPct','targetPortfolioPct']; const o={}; for(const k of keep) if(Object.prototype.hasOwnProperty.call(x,k)) o[k]=x[k]; console.log(JSON.stringify(o));} catch(e){}
NODE
done

echo '=== MICRO LIVE LOG MARKERS ==='
for f in /var/log/meme-alpha/micro-live.log /var/log/meme-alpha/micro-live-error.log; do
 [ -r "$f" ] || continue
 echo "--- $f"
 tail -n 250 "$f" | grep -Ei 'BLOCK|ALLOW|LIVE|EXEC|SKIP|SIGNAL|TREND|POLICY|SIGNER|ERROR|FAIL|READY|DRY|SHADOW' | tail -100 || true
done

echo '=== EXISTING RESTRICTED SUDO ==='
sudo -n -l 2>/dev/null | sed -n '1,120p' || true

echo 'V303_LIVE_PATH_AUDIT_PASS'
