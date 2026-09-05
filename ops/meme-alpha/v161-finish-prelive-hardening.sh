#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== FINISH v1.6 PRE-LIVE HARDENING ==='
for f in src/universe.js src/validation.js src/stress-test.js src/micro-live-gate.js; do
  [ -f "$f" ] || { echo "MISSING=$f"; exit 1; }
  chgrp meme-alpha-deploy "$f"
  chmod 664 "$f"
  node --check "$f"
done
node --input-type=module - <<'NODE'
import fs from 'node:fs';const p='package.json',j=JSON.parse(fs.readFileSync(p,'utf8'));j.scripts ||= {};j.scripts.stress='node src/stress-test.js';let c=j.scripts.cycle5||'';for(const s of ['src/stress-test.js','src/micro-live-gate.js']) c=c.replace(new RegExp(`\\s*&&\\s*node ${s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}`,'g'),'');c+=' && node src/stress-test.js && node src/micro-live-gate.js';j.scripts.cycle5=c;fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');console.log(`CYCLE5=${c}`);
NODE
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 110
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';for(const n of ['universe.json','validation.json','stress-test.json','micro-live-gate.json']){const p=`${R}/${n}`;if(!fs.existsSync(p))throw new Error(`MISSING_${n}`);const x=JSON.parse(fs.readFileSync(p));console.log(`--- ${n} ---`);console.log(JSON.stringify(x,null,2));}
const g=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`));const u=JSON.parse(fs.readFileSync(`${R}/universe.json`));if(g.version!=='1.6'||g.allowed!==false||g.currentMode!=='PAPER')throw new Error('GATE_INVARIANT');if(u.version!=='1.6'||u.unknownEntryEligible!==false)throw new Error('UNIVERSE_INVARIANT');console.log('V161_PRELIVE_HARDENING_PASS');
NODE
echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_LIVE_ENABLE=TRUE'
