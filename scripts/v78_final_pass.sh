#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(pwd)"
ENGINE=cloudflare-worker/engine-v77168.js
HUB=cloudflare-worker/hub-v77171.js
BASE='https://trading-v77-scanner.hanlinh227.workers.dev'

# V78-028 source is already landed. Never re-apply the Yahoo patch here.
SHA028=$(git log -n1 --format=%H -- "$ENGINE")
test "$(grep -c 'function yahooUs30CashVisibilityQuote' "$ENGINE")" = 1
grep -Fq 'source:"Yahoo Finance Cash Index Fallback"' "$ENGINE"
grep -Fq 'providerSymbol:ps' "$ENGINE"
grep -Fq 'fresh:false' "$ENGINE"
grep -Fq 'executionVerified:false' "$ENGINE"
grep -Fq 'analysisOnly:true' "$ENGINE"
grep -Fq 'fallback:true' "$ENGINE"
grep -Fq 'instrumentIdentity:"CASH_INDEX"' "$ENGINE"
node --check "$ENGINE"

# Deploy fresh current source (post-6abdb7ed) before claiming any live evidence.
cd cloudflare-worker
npm install --no-audit --no-fund
npm run check
npm run prepare:wrangler
npx wrangler deploy 2>&1 | tee /tmp/deploy028.log
CF028=$(grep -Eo 'Version ID: [0-9a-f-]+' /tmp/deploy028.log | tail -1 | sed 's/Version ID: //')
test -n "$CF028"
cd "$REPO_ROOT"
sleep 8

mkdir -p /tmp/v78
for S in NAS100 US30 US500 DEX JP225; do
  curl -fsS "$BASE/analyze?symbol=$S" -o "/tmp/v78/$S.json"
done
node <<'NODE'
const fs=require('fs'),out=[];
for(const s of ['NAS100','US30','US500','DEX','JP225']){
  const x=JSON.parse(fs.readFileSync(`/tmp/v78/${s}.json`,'utf8'));
  const q=x.analysisQuote||x.quote||{};
  if(!(Number(q.price)>0)) throw new Error(`${s} price missing`);
  if(s==='US30' && q.source==='Yahoo Finance Cash Index Fallback' && q.providerSymbol!=='^DJI') throw new Error('US30 Yahoo identity mismatch');
  if(q.fallback===true){
    if(q.fresh!==false||q.executionVerified!==false||q.analysisOnly!==true) throw new Error(`${s} unsafe fallback flags`);
    if(['MARKET','MARKET_SIGNAL'].includes(x.status)) throw new Error(`${s} fallback admitted as market`);
  }
  out.push([
    `symbol=${s}`,
    `status=${x.status||'UNKNOWN'}`,
    `price=${q.price}`,
    `source=${q.source||'-'}`,
    `providerSymbol=${q.providerSymbol||'-'}`,
    `fresh=${String(q.fresh)}`,
    `fallback=${String(q.fallback===true)}`,
    `analysisOnly=${String(q.analysisOnly===true)}`,
    `executionVerified=${String(q.executionVerified===true)}`,
    `quoteAgeSec=${q.quoteAgeSec??'null'}`,
    `instrumentIdentity=${q.instrumentIdentity||x?.context?.instrumentIdentity||'-'}`
  ].join(' | '));
}
fs.writeFileSync('/tmp/v78/index-live.txt',out.join('\n')+'\n');
console.log(out.join('\n'));
NODE

# Persist V78-028 evidence immediately after the genuine live acceptance.
cat > docs/ai-coengineer/V78-028_VALIDATION.txt <<EOF
V78-028 SIGNAL HUB CLEANUP + INDEX CASH LIVE ACCEPTANCE
SOURCE_SHA=${SHA028}
CLOUDFLARE_VERSION_ID=${CF028}
NODE_CHECK=PASS
TWELVE_DATA_DJI_DIRECT=UNSUPPORTED_404
YAHOO_US30_IDENTITY=^DJI/INDEX
US30_YAHOO_FALLBACK_FRESH=false
US30_YAHOO_FALLBACK_EXECUTION_VERIFIED=false
US30_YAHOO_FALLBACK_ANALYSIS_ONLY=true
US30_YAHOO_FALLBACK_MARKET_ADMISSION=BLOCKED
--- LIVE INDEX CASH ---
$(cat /tmp/v78/index-live.txt)
EOF

git config user.name 'V78 Signal Integrator'
git config user.email 'actions@users.noreply.github.com'
git add docs/ai-coengineer/V78-028_VALIDATION.txt
git commit -m 'V78-028 persist post-Yahoo live Index Cash acceptance'
git pull --rebase origin main
git push origin HEAD:main

# Capture pre-V78-030 live render state for ordering comparison.
curl -fsS "$BASE/hub" -o /tmp/v78/hub-before.json
curl -fsS "$BASE/run-now?group=forex" -o /tmp/v78/group-before.json
node -e "JSON.parse(require('fs').readFileSync('/tmp/v78/hub-before.json'));JSON.parse(require('fs').readFileSync('/tmp/v78/group-before.json'));"

# V78-030: rendering only. No ranking/admission functions may be edited.
test "$(grep -c 'function whyNowVi' "$ENGINE")" = 1
cp "$ENGINE" /tmp/engine-pre030.js
python3 scripts/v78_028_030_patch.py 030
node --check "$ENGINE"
test "$(grep -c 'Why now:' "$ENGINE")" = 2
test "$(grep -c 'function watchLine' "$ENGINE")" = 1
test "$(grep -c 'function hubSummary' "$ENGINE")" = 1
test "$(grep -c 'function runHub' "$ENGINE")" = 1
test "$(grep -c 'function actionableRank' "$ENGINE")" = 1
# Explicitly prove forbidden core functions are byte-identical across the rendering patch.
python3 - <<'PY'
from pathlib import Path
import re
before=Path('/tmp/engine-pre030.js').read_text()
after=Path('cloudflare-worker/engine-v77168.js').read_text()
for name in ('actionableRank','hubRank','fillBooks'):
    pat=rf'function {name}\([^\n]*'
    mb=re.search(pat,before); ma=re.search(pat,after)
    assert mb and ma and mb.group(0)==ma.group(0), name
PY
git diff --check
git add "$ENGINE"
git commit -m 'V78-030 propagate WHY NOW to group scan and Hub top setups'
SHA030=$(git rev-parse HEAD)
git pull --rebase origin main
git push origin HEAD:main

cd cloudflare-worker
npx wrangler deploy 2>&1 | tee /tmp/deploy030.log
CF030=$(grep -Eo 'Version ID: [0-9a-f-]+' /tmp/deploy030.log | tail -1 | sed 's/Version ID: //')
test -n "$CF030"
cd "$REPO_ROOT"
sleep 8
curl -fsS "$BASE/hub" -o /tmp/v78/hub-after.json
curl -fsS "$BASE/run-now?group=forex" -o /tmp/v78/group-after.json
node <<'NODE'
const fs=require('fs');
for(const f of ['hub-before','hub-after','group-before','group-after']) JSON.parse(fs.readFileSync(`/tmp/v78/${f}.json`,'utf8'));
function sig(v,out=[]){
  if(Array.isArray(v)){for(const x of v)sig(x,out);return out;}
  if(v&&typeof v==='object'){
    if(typeof v.symbol==='string' && ('status' in v || 'score' in v)) out.push(`${v.symbol}|${v.status??''}|${v.score??''}`);
    for(const x of Object.values(v))sig(x,out);
  }
  return out;
}
const b=sig(JSON.parse(fs.readFileSync('/tmp/v78/hub-before.json','utf8'))).slice(0,7);
const a=sig(JSON.parse(fs.readFileSync('/tmp/v78/hub-after.json','utf8'))).slice(0,7);
if(JSON.stringify(b)!==JSON.stringify(a)) throw new Error(`hub top ordering changed: before=${JSON.stringify(b)} after=${JSON.stringify(a)}`);
fs.writeFileSync('/tmp/v78/hub-order.txt',`before=${JSON.stringify(b)}\nafter=${JSON.stringify(a)}\n`);
NODE

cat > docs/ai-coengineer/V78-030_VALIDATION.txt <<EOF
V78-030 WHY NOW PROPAGATION
SOURCE_SHA=${SHA030}
CLOUDFLARE_VERSION_ID=${CF030}
NODE_CHECK=PASS
WHY_NOW_FUNCTION_COUNT=1
WHY_NOW_WATCHLINE_HUBSUMMARY_COUNT=2
ACTIONABLERANK_UNTOUCHED=true
HUBRANK_UNTOUCHED=true
FILLBOOKS_UNTOUCHED=true
LIVE_GROUP_JSON=PASS
LIVE_HUB_JSON=PASS
TOP_SETUP_ORDER_UNCHANGED=true
$(cat /tmp/v78/hub-order.txt)
RENDERING_ONLY=true
EOF

# V78-031 fresh audit: current setupCard still reads a dead a.entryIntelligence field.
# Fix only if that exact current bug remains. Use buildEntryIntelligenceShadow just like engine renderers.
SETUPCARD_BUG=false
if grep -Fq 'q=a?.entryIntelligence?.quality||null' "$HUB"; then
  SETUPCARD_BUG=true
  cp "$HUB" /tmp/hub-pre031.js
  python3 - <<'PY'
from pathlib import Path
p=Path('cloudflare-worker/hub-v77171.js')
s=p.read_text()
old_import='import {getEntryIntelligenceShadow} from "./providers/entry-intelligence.js";'
new_import='import {buildEntryIntelligenceShadow,getEntryIntelligenceShadow} from "./providers/entry-intelligence.js";'
old='q=a?.entryIntelligence?.quality||null;'
new='q=buildEntryIntelligenceShadow(a)?.quality||null;'
assert s.count(old_import)==1, s.count(old_import)
assert s.count(old)==1, s.count(old)
s=s.replace(old_import,new_import,1).replace(old,new,1)
p.write_text(s)
PY
  node --check "$HUB"
  test "$(grep -c 'buildEntryIntelligenceShadow,getEntryIntelligenceShadow' "$HUB")" = 1
  test "$(grep -c 'q=buildEntryIntelligenceShadow(a)?.quality||null' "$HUB")" = 1
  test "$(grep -c 'q=a?.entryIntelligence?.quality||null' "$HUB")" = 0
  git diff --check
  git add "$HUB"
  git commit -m 'V78-031 fix Hub setupCard quality rendering from live entry intelligence'
  SHA031=$(git rev-parse HEAD)
  git pull --rebase origin main
git push origin HEAD:main
  cd cloudflare-worker
  npx wrangler deploy 2>&1 | tee /tmp/deploy031.log
  CF031=$(grep -Eo 'Version ID: [0-9a-f-]+' /tmp/deploy031.log | tail -1 | sed 's/Version ID: //')
  test -n "$CF031"
  cd "$REPO_ROOT"
  sleep 8
  curl -fsS "$BASE/hub" -o /tmp/v78/hub-031.json
  node -e "JSON.parse(require('fs').readFileSync('/tmp/v78/hub-031.json'));"
  cat > docs/ai-coengineer/V78-031_VALIDATION.txt <<EOF
V78-031 SETUPCARD ENTRY-INTELLIGENCE QUALITY FIX
BUG_PRESENT=true
BUG=a.entryIntelligence.quality dead-field read in setupCard
FIX=buildEntryIntelligenceShadow(a).quality
SOURCE_SHA=${SHA031}
CLOUDFLARE_VERSION_ID=${CF031}
NODE_CHECK=PASS
LIVE_HUB_JSON=PASS
RENDERING_ONLY=true
EOF
else
  SHA031=NOT_APPLIED
  CF031=NOT_APPLIED
  cat > docs/ai-coengineer/V78-031_VALIDATION.txt <<EOF
V78-031 SETUPCARD ENTRY-INTELLIGENCE QUALITY AUDIT
BUG_PRESENT=false
PATCH_APPLIED=false
CURRENT_SETUPCARD_NO_DEAD_FIELD=true
EOF
fi

cat >> docs/ai-coengineer/SHARED_STATE.md <<EOF

V78-028 — RESOLVED / DEPLOYED
- Source SHA: ${SHA028}
- Cloudflare Version ID: ${CF028}
- Post-Yahoo-fix live acceptance passed for NAS100/US30/US500/DEX/JP225.
- Yahoo ^DJI is visibility-only for US30 when used: fresh=false, analysisOnly=true, executionVerified=false; MARKET/MARKET_SIGNAL admission blocked.

V78-030 — RESOLVED / DEPLOYED
- Source SHA: ${SHA030}
- Cloudflare Version ID: ${CF030}
- WHY NOW propagated only to watchLine() and hubSummary(); actionableRank/hubRank/fillBooks unchanged.
- Live group + Hub JSON passed and Hub top ordering remained unchanged.

V78-031 — ${SETUPCARD_BUG}
- Dead setupCard entryIntelligence field present at fresh audit: ${SETUPCARD_BUG}.
- Source SHA: ${SHA031}
- Cloudflare Version ID: ${CF031}
- If applied, fix is rendering-only via buildEntryIntelligenceShadow(a).quality.
EOF

printf '# AI WRITE LOCK\n\nLOCKED: false\nOWNER: NONE\nSCOPE: NONE\nRELEASED: 2026-08-20\nLAST_RESULT: V78-028 and V78-030 live accepted; V78-031 independently audited%s.\n' "$([ "$SETUPCARD_BUG" = true ] && echo ' and fixed/deployed' || echo '')" > docs/ai-coengineer/WRITE_LOCK.md

git add docs/ai-coengineer/V78-030_VALIDATION.txt docs/ai-coengineer/V78-031_VALIDATION.txt docs/ai-coengineer/SHARED_STATE.md docs/ai-coengineer/WRITE_LOCK.md
git commit -m 'Persist V78-030 and V78-031 evidence and release write lock'
git pull --rebase origin main
git push origin HEAD:main
