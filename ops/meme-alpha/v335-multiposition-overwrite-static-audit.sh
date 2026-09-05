#!/usr/bin/env bash
set -euo pipefail
F=/opt/meme-alpha/app/src/micro-live-executor.js
echo '=== V335 MULTIPOSITION OVERWRITE STATIC AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ
node - "$F" <<'NODE'
const fs=require('fs'); const f=process.argv[2]; const s=fs.readFileSync(f,'utf8');
const checks={
  version331:/3\.31|V331|MULTI.POSITION/i.test(s),
  positionsArray:/st\.positions/.test(s),
  legacyMigration:/st\.position/.test(s)&&/positions/.test(s),
  duplicateMintGuard:/positions[^\n]{0,200}(some|find)[^\n]{0,200}mint|some\([^\n]*mint|find\([^\n]*mint/i.test(s),
  appendEntry:/positions\.(push|concat)|\.positions\s*=\s*\[\.\.\./i.test(s),
  perPositionLoop:/for\s*\([^)]*(position|pos)[^)]*of\s+[^)]*positions|positions\.(map|filter|forEach)/i.test(s),
  removeByMintOrId:/filter\([^\n]{0,250}(mint|id)|splice\(/i.test(s),
  noHardMax:/maxPositions/i.test(s)===false,
  exitReserve:/EXIT_RESERVE|exitReserve|reserve.*position/i.test(s),
};
for(const [k,v] of Object.entries(checks)) console.log(`${k}=${v}`);
// Print only relevant state mutation lines, no secrets.
const lines=s.split(/\r?\n/); lines.forEach((l,i)=>{if(/st\.positions|positions\.(push|filter|splice)|st\.position\b|exitReserve|EXIT_RESERVE/i.test(l)) console.log(`L${i+1}: ${l.trim().slice(0,400)}`)});
if(!checks.version331||!checks.positionsArray||!checks.appendEntry||!checks.perPositionLoop||!checks.exitReserve) process.exit(2);
console.log('V335_STATIC_OVERWRITE_AUDIT_PASS');
NODE
# Runtime process/gate only; state itself remains protected.
echo EXECUTOR_PROCESSES=$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)
echo SIGNER_PROCESSES=$(pgrep -fc '/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py' || true)
node - <<'NODE'
const fs=require('fs');try{const g=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));console.log('GATE_ALLOWED='+g.allowed);console.log('GATE_REASONS='+JSON.stringify(g.reasons||[]));}catch(e){console.log('GATE_READ_ERROR='+e.message)}
NODE
