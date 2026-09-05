#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
cd "$APP"

echo '=== MEME ALPHA COMPLETION AUDIT ==='
echo "RUNNER_USER=$(id -un) UID=$(id -u)"
echo "PAPER_SERVICE=$(systemctl is-active meme-alpha-paper.service || true)"
echo "SIGNER_SERVICE=$(systemctl is-active meme-alpha-signer.service || true)"
echo "RUNNER_SERVICE=$(systemctl is-active actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service || true)"

echo '=== RUNTIME ==='
cat config/runtime.json

echo '=== PACKAGE ==='
cat package.json

echo '=== STATE SUMMARY ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const P='/var/lib/meme-alpha/data/paper';
const read=(n,d={})=>{try{return JSON.parse(fs.readFileSync(`${P}/${n}`,'utf8'))}catch{return d}};
const s=read('state.json'); const v=read('validation.json'); const h=read('scanner-source-health.json'); const r=read('risk-state.json'); const g=read('micro-live-gate.json'); const st=read('stress-test.json');
console.log(JSON.stringify({
 state:{equity:s.equitySol??s.equity??null,openPositions:Array.isArray(s.openPositions)?s.openPositions.length:null,trades:s.trades?.length??null,realized:s.realizedPnlSol??null},
 validation:v,source:h,risk:r,gate:g,stress:st
},null,2));
NODE

echo '=== PYTHON SIGNING LIBS ==='
python3 - <<'PY'
mods=['nacl','solders','solana']
for m in mods:
 try:
  x=__import__(m); print(f'{m}=YES version={getattr(x,"__version__","")}')
 except Exception as e: print(f'{m}=NO {type(e).__name__}')
PY

echo '=== NODE SOLANA LIBS ==='
node --input-type=module - <<'NODE'
for (const m of ['@solana/kit','@solana/web3.js','tweetnacl']) {
 try { const x=await import(m); console.log(`${m}=YES`); } catch(e) { console.log(`${m}=NO`); }
}
NODE

echo '=== SOURCE EXCERPTS ==='
for f in src/universe.js src/security.js src/token2022-audit.js src/holder-cluster.js src/risk.js src/position.js src/validation.js src/micro-live-gate.js; do
 echo "--- $f ---"; [ -f "$f" ] && sed -n '1,260p' "$f" || echo MISSING; done

echo '=== PERMS ==='
namei -l /var/lib/meme-alpha-signer/keys || true
namei -l /run/meme-alpha-signer/signer.sock || true
stat -c '%U:%G %a %n' /opt/meme-alpha/app /var/lib/meme-alpha/data/paper /var/lib/meme-alpha-signer/keys /run/meme-alpha-signer/signer.sock 2>/dev/null || true

echo 'V150_AUDIT_COMPLETE'
