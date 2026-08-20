#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(pwd)"
ENGINE=cloudflare-worker/engine-v77168.js
# Provider evidence already proved Twelve Data rejects DJI, while Yahoo ^DJI returns instrumentType=INDEX.
python3 scripts/v78_028_us30_yahoo_cash_patch.py
node --check "$ENGINE"
test "$(grep -c 'function yahooUs30CashVisibilityQuote' "$ENGINE")" = 1
grep -Fq 'providerSymbol:ps' "$ENGINE"
grep -Fq 'instrumentIdentity:"CASH_INDEX"' "$ENGINE"
grep -Fq 'source:"Yahoo Finance Cash Index Fallback"' "$ENGINE"
grep -Fq 'fresh:false' "$ENGINE"
grep -Fq 'executionVerified:false' "$ENGINE"
grep -Fq 'analysisOnly:true' "$ENGINE"
grep -Fq 'fallback:true' "$ENGINE"
git config user.name 'V78 Signal Integrator'
git config user.email 'actions@users.noreply.github.com'
git add "$ENGINE"
git commit -m 'V78-028 resolve US30 with verified Yahoo cash-index visibility fallback'
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
  if(s==='US30' && q.source==='Yahoo Finance Cash Index Fallback' && q.providerSymbol!=='^DJI') throw new Error('US30 Yahoo identity mismatch');
  out.push(`${s} status=${x.status||'UNKNOWN'} price=${q.price} source=${q.source||'-'} provider=${q.providerSymbol||'-'} fresh=${String(q.fresh)} fallback=${String(q.fallback===true)} interval=${q.fallbackInterval||'native'} age=${q.quoteAgeSec??'null'}`);
}
fs.writeFileSync('/tmp/v78/index-live.txt',out.join('\n')+'\n'); console.log(out.join('\n'));
NODE
# V78-030 is strictly dependent on V78-028 passing above.
test "$(grep -c 'function whyNowVi' "$ENGINE")" = 1
python3 scripts/v78_028_030_patch.py 030
node --check "$ENGINE"
test "$(grep -c 'Why now:' "$ENGINE")" = 2
test "$(grep -c 'function watchLine' "$ENGINE")" = 1
test "$(grep -c 'function hubSummary' "$ENGINE")" = 1
test "$(grep -c 'function runHub' "$ENGINE")" = 1
test "$(grep -c 'function actionableRank' "$ENGINE")" = 1
git diff --check
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
node -e "JSON.parse(require('fs').readFileSync('/tmp/v78/forex.json'));JSON.parse(require('fs').readFileSync('/tmp/v78/hub.json'));console.log('V78-030 live JSON PASS')"
git pull --rebase origin main
{
  echo 'V78-028 HOTFIX'; echo "SOURCE_SHA=$SHA028"; echo "CLOUDFLARE_VERSION_ID=$CF028"; echo 'TWELVE_DATA_DJI_DIRECT=UNSUPPORTED_404'; echo 'YAHOO_US30_IDENTITY=^DJI/INDEX'; cat /tmp/v78/index-live.txt;
} > docs/ai-coengineer/V78-028_HOTFIX_VALIDATION.txt
{
  echo 'V78-030'; echo "SOURCE_SHA=$SHA030"; echo "CLOUDFLARE_VERSION_ID=$CF030"; echo 'NODE_CHECK=PASS'; echo 'WHY_NOW_WATCHLINE_HUBSUMMARY_COUNT=2'; echo 'LIVE_GROUP_JSON=PASS'; echo 'LIVE_HUB_JSON=PASS'; echo 'RENDERING_ONLY=true';
} > docs/ai-coengineer/V78-030_VALIDATION.txt
cat >> docs/ai-coengineer/SHARED_STATE.md <<EOF

V78-028 FINAL — RESOLVED / DEPLOYED
- Source: $SHA028
- Cloudflare Version ID: $CF028
- Twelve Data DJI was proven unsupported by direct sanitized provider diagnostics; US30 price visibility now uses verified Yahoo ^DJI INDEX only after existing native providers fail.
- All five CASH INDEX symbols passed positive-price live validation; any fallback remains fresh=false / analysisOnly=true / executionVerified=false and cannot enter MARKET/MARKET_SIGNAL.

V78-030 — RESOLVED / DEPLOYED
- Source: $SHA030
- Cloudflare Version ID: $CF030
- WHY NOW propagated to watchLine and hubSummary; rendering-only, ranking/admission untouched.
EOF
printf '# AI WRITE LOCK\n\nLOCKED: false\nOWNER: NONE\nSCOPE: NONE\nRELEASED: 2026-08-20\nLAST_RESULT: V78-028 final and V78-030 resolved/deployed.\n' > docs/ai-coengineer/WRITE_LOCK.md
git add docs/ai-coengineer/V78-028_HOTFIX_VALIDATION.txt docs/ai-coengineer/V78-030_VALIDATION.txt docs/ai-coengineer/SHARED_STATE.md docs/ai-coengineer/WRITE_LOCK.md
git commit -m 'V78-028 V78-030 persist final evidence and release lock'
git push origin HEAD:main
