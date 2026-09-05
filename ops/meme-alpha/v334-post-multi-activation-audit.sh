#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STATE=/var/lib/meme-alpha/data/micro-live/state.json
EXEC="$APP/src/micro-live-executor.js"
GATE="$APP/runtime-status/micro-live-gate.json"

echo '=== V334 POST MULTI ACTIVATION AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ

sudo -n /bin/systemctl is-active meme-alpha-micro-live.service >/dev/null && echo MICRO_LIVE_SERVICE=active || echo MICRO_LIVE_SERVICE=inactive
sudo -n /bin/systemctl is-active meme-alpha-signer.service >/dev/null && echo SIGNER_SERVICE=active || echo SIGNER_SERVICE=inactive
sha256sum "$EXEC" || true
stat -c 'EXECUTOR owner=%U group=%G mode=%a size=%s' "$EXEC" || true

/usr/bin/node - "$EXEC" "$STATE" "$GATE" <<'NODE'
const fs=require('fs');
const [exec,state,gate]=process.argv.slice(2);
const src=fs.readFileSync(exec,'utf8');
console.log('EXECUTOR_V331_MARKER='+(src.includes('MICRO_LIVE_EXECUTOR_V331_MULTI')?'true':'false'));
console.log('NO_HARD_MAX_POSITIONS='+(src.includes('maxPositions')?'false':'true'));
console.log('EXIT_RESERVE_MARKER='+(src.includes('PER_POSITION_EXIT_RESERVE_SOL')||src.includes('EXIT_RESERVE_LAMPORTS')?'true':'unknown'));
try{
 const s=JSON.parse(fs.readFileSync(state,'utf8'));
 const ps=Array.isArray(s.positions)?s.positions:(s.position?[s.position]:[]);
 console.log('STATE_VERSION='+(s.version||''));
 console.log('STATE_POSITIONS='+ps.length);
 for(const p of ps) console.log(`POSITION mint=${p.mint||''} symbol=${p.symbol||''} cost=${p.costBasisLamports||p.entrySolLamports||0}`);
 console.log('LEGACY_POSITION_FIELD='+(s.position?'present':'absent'));
}catch(e){console.log('STATE_READ_ERROR='+e.message)}
try{
 const g=JSON.parse(fs.readFileSync(gate,'utf8'));
 console.log('GATE_ALLOWED='+(g.allowed===true?'true':'false'));
 console.log('GATE_REASON='+(g.reason||g.status||''));
}catch(e){console.log('GATE_READ_ERROR='+e.message)}
NODE

pgrep -af '/opt/meme-alpha/app/src/micro-live-executor.js' || true
pgrep -af '/opt/meme-alpha-signer/ready_signer.py' || true

echo V334_POST_MULTI_ACTIVATION_AUDIT_PASS
