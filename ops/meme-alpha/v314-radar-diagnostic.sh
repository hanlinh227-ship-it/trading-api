#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
cd "$APP"
echo '=== V314 RADAR DIAGNOSTIC ==='
echo "user=$(id -un) groups=$(id -Gn)"
echo '=== SERVICE ==='
sudo -n /bin/systemctl is-active meme-alpha-paper.service || true
systemctl show meme-alpha-paper.service -p User -p Group -p ExecStart -p MainPID -p ActiveState -p SubState --no-pager || true
stat -c '%n owner=%U group=%G mode=%a' "$APP" "$APP/src" "$APP/runtime-status" "$DATA" 2>/dev/null || true
for p in "$APP/runtime-status/new-listing-radar.json" "$DATA/new-listing-radar.json"; do
  if [ -e "$p" ]; then stat -c '%n owner=%U group=%G mode=%a size=%s' "$p"; head -60 "$p"; else echo "$p ABSENT"; fi
done

echo '=== DEX ENDPOINTS FROM VPS ==='
node - <<'NODE'
const endpoints=[
 ['profile','https://api.dexscreener.com/token-profiles/latest/v1'],
 ['boost','https://api.dexscreener.com/token-boosts/latest/v1'],
 ['community','https://api.dexscreener.com/community-takeovers/latest/v1']
];
for(const [name,url] of endpoints){
 try{const t=Date.now();const r=await fetch(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(5000)});const text=await r.text();let rows=-1;try{const x=JSON.parse(text);rows=Array.isArray(x)?x.length:(x&&typeof x==='object'?1:0)}catch{};console.log(`${name} http=${r.status} ms=${Date.now()-t} bytes=${text.length} rows=${rows} head=${text.slice(0,120).replace(/\s+/g,' ')}`)}catch(e){console.log(`${name} ERROR=${e?.name}:${e?.message}`)}
}
NODE

echo '=== RECENT JOURNAL RADAR ==='
journalctl -u meme-alpha-paper.service --since '15 minutes ago' --no-pager 2>/dev/null | grep -Ei 'RADAR|new-listing|permission|EACCES|ENOENT|HTTP_|cycle failed' | tail -120 || true

echo 'V314_RADAR_DIAGNOSTIC_PASS'
