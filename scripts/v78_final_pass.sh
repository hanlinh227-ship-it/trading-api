#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(pwd)"
ENGINE=cloudflare-worker/engine-v77168.js
python3 scripts/v78_028_quote_visibility_final.py
node --check "$ENGINE"
grep -Fq 'function tdIndexQuoteVisibilityFallback' "$ENGINE"
git config user.name 'V78 Signal Integrator'
git config user.email 'actions@users.noreply.github.com'
git add "$ENGINE"
git commit -m 'V78-028 final Index Cash quote visibility fallback'
SHA028=$(git rev-parse HEAD)
git push origin HEAD:main
cd cloudflare-worker
npm install --no-audit --no-fund
npm run check
npm run prepare:wrangler
npx wrangler deploy 2>&1 | tee /tmp/deploy028.log
CF028=$(grep -Eo 'Version ID: [0-9a-f-]+' /tmp/deploy028.log | tail -1 | sed 's/Version ID: //')
test -n "$CF028"
cd "$REPO_ROOT"
sleep 8
BASE='https://trading-v77-scanner.hanlinh227.workers.dev'
mkdir -p /tmp/v78
for S in NAS100 US30 US500 DEX JP225; do curl -fsS "$BASE/analyze?symbol=$S" -o "/tmp/v78/$S.json"; done
node <<'NODE'
const fs=require('fs'),out=[];
for(const s of ['NAS100','US30','US500','DEX','JP225']){
  const x=JSON.parse(fs.readFileSync(`/tmp/v78/${s}.json`,'utf8')); const q=x.analysisQuote||x.quote||{};
  if(!(Number(q.price)>0)) throw new Error(`${s} price missing`);
  if(q.fallback===true){ if(q.fresh!==false||q.executionVerified!==false||q.analysisOnly!==true) throw new Error(`${s} unsafe fallback`); if(['MARKET','MARKET_SIGNAL'].includes(x.status)) throw new Error(`${s} fallback market admission`); }
  out.push(`${s} status=${x.status||'UNKNOWN'} price=${q.price} source=${q.source||'-'} fresh=${String(q.fresh)} fallback=${String(q.fallback===true)} interval=${q.fallbackInterval||'native'} age=${q.quoteAgeSec??'null'}`);
}
fs.writeFileSync('/tmp/v78/index-live.txt',out.join('\n')+'\n'); console.log(out.join('\n'));
NODE
test "$(grep -c 'function whyNowVi' "$ENGINE")" = 1
python3 scripts/v78_028_030_patch.py 030
node --check "$ENGINE"
test "$(grep -c 'Why now:' "$ENGINE")" = 2
git add "$ENGINE"
git commit -m 'V78-030 propagate WHY NOW to group scan and Hub top setups'
SHA030=$(git rev-parse HEAD)
git push origin HEAD:main
cd cloudflare-worker
npx wrangler deploy 2>&1 | tee /tmp/deploy030.log
CF030=$(grep -Eo 'Version ID: [0-9a-f-]+' /tmp/deploy030.log | tail -1 | sed 's/Version ID: //')
test -n "$CF030"
cd "$REPO_ROOT"
sleep 8
curl -fsS "$BASE/run-now?group=forex" -o /tmp/v78/forex.json
curl -fsS "$BASE/hub" -o /tmp/v78/hub.json
node -e "JSON.parse(require('fs').readFileSync('/tmp/v78/forex.json'));JSON.parse(require('fs').readFileSync('/tmp/v78/hub.json'))"
git pull --rebase origin main
{
  echo 'V78-028 HOTFIX'; echo "SOURCE_SHA=$SHA028"; echo "CLOUDFLARE_VERSION_ID=$CF028"; cat /tmp/v78/index-live.txt;
} > docs/ai-coengineer/V78-028_HOTFIX_VALIDATION.txt
{
  echo 'V78-030'; echo "SOURCE_SHA=$SHA030"; echo "CLOUDFLARE_VERSION_ID=$CF030"; echo 'NODE_CHECK=PASS'; echo 'LIVE_GROUP_JSON=PASS'; echo 'LIVE_HUB_JSON=PASS';
} > docs/ai-coengineer/V78-030_VALIDATION.txt
cat >> docs/ai-coengineer/SHARED_STATE.md <<EOF

V78-028 FINAL — RESOLVED / DEPLOYED
- Source: $SHA028
- Cloudflare Version ID: $CF028
- All five CASH INDEX symbols passed positive-price live validation; fallback remains fresh=false and analysis-only.

V78-030 — RESOLVED / DEPLOYED
- Source: $SHA030
- Cloudflare Version ID: $CF030
- WHY NOW propagated to watchLine and hubSummary; rendering-only.
EOF
printf '# AI WRITE LOCK\n\nLOCKED: false\nOWNER: NONE\nSCOPE: NONE\nRELEASED: 2026-08-20\nLAST_RESULT: V78-028 final and V78-030 resolved/deployed.\n' > docs/ai-coengineer/WRITE_LOCK.md
git add docs/ai-coengineer/V78-028_HOTFIX_VALIDATION.txt docs/ai-coengineer/V78-030_VALIDATION.txt docs/ai-coengineer/SHARED_STATE.md docs/ai-coengineer/WRITE_LOCK.md
git commit -m 'V78-028 V78-030 persist final evidence and release lock'
git push origin HEAD:main
