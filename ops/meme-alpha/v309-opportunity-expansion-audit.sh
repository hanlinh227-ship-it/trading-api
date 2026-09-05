#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V309 OPPORTUNITY EXPANSION AUDIT ==='
echo "host=$(hostname) user=$(id -un) at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo '=== DEPENDENCIES ==='
[ -r package.json ] && node - <<'NODE'
const p=require('/opt/meme-alpha/app/package.json'); console.log(JSON.stringify({dependencies:p.dependencies||{},devDependencies:p.devDependencies||{}},null,2));
NODE

echo '=== PROVIDER CAPABILITY (presence only, no secrets) ==='
for k in HELIUS_API_KEY HELIUS_RPC_URL HELIUS_WSS_URL JUPITER_API_KEY JUP_API_KEY BIRDEYE_API_KEY DEXSCREENER_API_KEY SOLANA_RPC_URL; do
  if systemctl show meme-alpha-paper.service -p Environment 2>/dev/null | grep -q "${k}="; then echo "$k=PRESENT_SERVICE";
  elif [ -n "${!k:-}" ]; then echo "$k=PRESENT_RUNNER"; else echo "$k=ABSENT_OR_NOT_EXPOSED"; fi
done

echo '=== UNIVERSE ==='
nl -ba src/universe.js | sed -n '1,280p'
echo '=== RISK ==='
nl -ba src/risk.js | sed -n '1,320p'
echo '=== SAFE SIGNAL EXPORT ==='
nl -ba src/safe-signal-export.js | sed -n '1,280p'
echo '=== POSITION SIZING / ENTRY EXCERPTS ==='
grep -nEi 'size|equity|balance|exposure|allocation|risk|buy|entry|scale|position' src/position.js | head -220 || true

echo '=== RUNTIME CONFIG SAFE ==='
node - <<'NODE'
const fs=require('fs'); const p='/opt/meme-alpha/app/config/runtime.json';
try{const x=JSON.parse(fs.readFileSync(p,'utf8')); const deny=/key|secret|token|private|seed|mnemonic|url|endpoint/i; const o={}; for(const [k,v] of Object.entries(x)) if(!deny.test(k)) o[k]=v; console.log(JSON.stringify(o,null,2));}catch(e){console.log('RUNTIME_READ_FAIL')}
NODE

echo 'V309_OPPORTUNITY_EXPANSION_AUDIT_PASS'
