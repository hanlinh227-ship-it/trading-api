#!/usr/bin/env bash
set -euo pipefail
F=/opt/meme-alpha/app/run-paper.sh
echo '=== V338 FAST SIGNAL TOPOLOGY AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ
stat -c 'RUN_PAPER %U:%G %a %s' "$F"
awk 'NR<=260{print NR ":" $0}' "$F" | grep -E 'LIVE_SIGNAL_MAX_AGE_SEC|FAST_GUARD|FULL_CYCLE|cycle5|scanner|signal|sleep|paperExecutionEnabled|position.js|while|mode=' || true
for i in 1 2 3 4; do
  node - <<'NODE'
const fs=require('fs');const p='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';try{const s=JSON.parse(fs.readFileSync(p,'utf8'));const ts=s.timestamp||s.generatedAt;console.log(`SAMPLE ts=${ts} age=${((Date.now()-Date.parse(ts))/1000).toFixed(2)} candidates=${(s.candidates||[]).length}`)}catch(e){console.log('SAMPLE_ERR='+e.message)}
NODE
  sleep 5
done
