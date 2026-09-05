#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app

echo '=== V299 MEME ALPHA RUNTIME DISCOVERY ==='
echo "user=$(id -un) uid=$(id -u) host=$(hostname)"
[ -d "$APP" ] || { echo 'APP_MISSING'; exit 2; }

cd "$APP"

echo '=== MEME ALPHA SYSTEMD UNITS ==='
systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk 'tolower($0) ~ /meme|alpha/ {print}' | head -80 || true
systemctl list-units --type=service --all --no-legend 2>/dev/null | awk 'tolower($0) ~ /meme|alpha/ {print}' | head -80 || true

echo '=== PACKAGE SCRIPTS (SAFE) ==='
node - <<'NODE' 2>/dev/null || true
const fs=require('fs');
try {
  const p=JSON.parse(fs.readFileSync('package.json','utf8'));
  console.log(JSON.stringify({name:p.name,version:p.version,scripts:p.scripts||{}},null,2));
} catch(e) { console.log('PACKAGE_READ_SKIP'); }
NODE

echo '=== SCANNER / SIGNAL CANDIDATES ==='
find "$APP" -maxdepth 4 -type f \
  \( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' -o -name '*.json' \) \
  ! -path '*/node_modules/*' ! -path '*/.git/*' \
  ! -name '.env*' ! -iname '*secret*' ! -iname '*private*' ! -iname '*wallet*' ! -iname '*key*' \
  -print0 | while IFS= read -r -d '' f; do
    if grep -qiE 'signal-snapshot|SCAN_INTERVAL|SIGNAL_INTERVAL|POLL_INTERVAL|REFRESH_INTERVAL|scanner|shadowReady|liveExecution' "$f" 2>/dev/null; then
      rel="${f#$APP/}"
      echo "--- $rel"
      grep -nEi 'signal-snapshot|SCAN_INTERVAL|SIGNAL_INTERVAL|POLL_INTERVAL|REFRESH_INTERVAL|shadowReady|liveExecution' "$f" 2>/dev/null | head -40 || true
    fi
  done

echo '=== SAFE POLICY SHAPE ==='
if [ -r /etc/meme-alpha/micro-live-policy.json ]; then
  node - <<'NODE' 2>/dev/null || true
const fs=require('fs');
try {
 const p=JSON.parse(fs.readFileSync('/etc/meme-alpha/micro-live-policy.json','utf8'));
 const allow=['enabled','liveExecution','mode','maxNotionalUsd','maxPositionUsd','maxWalletExposurePct','maxPriceImpactPct','maxSlippageBps','maxDailyLossUsd','maxDailyLossPct','requireSecurityPass','requireSellRoute','requireHolderClusterPass','token2022Policy','minSignalFreshnessSec','maxSignalAgeSec','maxTrendAgeSec','jitoEnabled','mevProtection','executor'];
 const out={}; for(const k of allow) if(Object.prototype.hasOwnProperty.call(p,k)) out[k]=p[k];
 console.log(JSON.stringify(out,null,2));
} catch(e){console.log('POLICY_PARSE_SKIP')}
NODE
else
  echo 'POLICY_NOT_READABLE'
fi

echo '=== STATE / FRESHNESS CANDIDATES ==='
for f in state/signal-snapshot.json state/trend-snapshot.json state/shadow-ready*.json state/*allocator*.json; do
  [ -f "$f" ] || continue
  echo "--- $f"
  node - "$f" <<'NODE' 2>/dev/null || true
const fs=require('fs'); const f=process.argv[2];
try { const x=JSON.parse(fs.readFileSync(f,'utf8'));
 const keys=['ts','timestamp','updatedAt','generatedAt','signalAgeSec','trendAgeSec','universeSize','eligibleCount','shadowReady','liveExecution','reason','mode'];
 const out={}; for(const k of keys) if(Object.prototype.hasOwnProperty.call(x,k)) out[k]=x[k];
 console.log(JSON.stringify(out)); } catch(e){}
NODE
done

echo '=== RESTRICTED SUDO CAPABILITY ==='
if sudo -n true 2>/dev/null; then echo 'SUDO_NONINTERACTIVE_TRUE'; else echo 'SUDO_NONINTERACTIVE_FALSE'; fi
sudo -n -l 2>/dev/null | sed -n '1,120p' || true

echo 'V299_RUNTIME_DISCOVERY_PASS'
