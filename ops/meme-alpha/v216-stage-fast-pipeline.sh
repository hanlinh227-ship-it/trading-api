#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo '=== MEME ALPHA v2.16 FAST PIPELINE STAGE ==='
SCANNER_SRC="$APP/src/scanner.js"
SCANNER_DST="$APP/ops/meme-alpha/scanner-v216-fast.js"
HOLDER_STAGE="$APP/ops/meme-alpha/holder-cluster-v215.js"
[ -f "$SCANNER_SRC" ] || { echo ABORT_SCANNER_MISSING; exit 1; }
[ -f "$HOLDER_STAGE" ] || { echo ABORT_HOLDER_V215_NOT_STAGED; exit 1; }
cp "$SCANNER_SRC" "$SCANNER_DST"
python3 - "$SCANNER_DST" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
if 'SCANNER_FAST_PIPELINE_V216' in s:
 print('ALREADY_PATCHED_V216=TRUE');sys.exit(0)
# Keep Jupiter request pacing conservative, but make a dead request bounded.
s=s.replace('const maxAttempts = 3;','const maxAttempts = 2;',1)
s=s.replace('        12000\n      );','        6000\n      );',1)
# Add one/two-request DEX Screener batch enrichment. This replaces up to 40
# sequential per-token HTTP calls without weakening the DEX/liquidity gate.
marker='console.log("=== MEME ALPHA SCANNER v0.2 ===");'
fn=r'''
// SCANNER_FAST_PIPELINE_V216
async function dexBatchChecks(items) {
  const out = new Map();
  const mints = [...new Set(items.map(x=>x?.result?.mint).filter(Boolean))];
  for (let i=0; i<mints.length; i+=30) {
    const chunk=mints.slice(i,i+30);
    const url=`${cfg.dexscreener}/tokens/v1/solana/${chunk.join(',')}`;
    try {
      const r=await fetch(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(5000)});
      if(!r.ok) throw new Error(`DEX_BATCH_HTTP_${r.status}`);
      const rows=await r.json();
      const pairs=Array.isArray(rows)?rows:[];
      for(const mint of chunk){
        const xs=pairs.filter(q=>q?.chainId==='solana'&&(q?.baseToken?.address===mint||q?.quoteToken?.address===mint)).sort((a,b)=>n(b?.liquidity?.usd)-n(a?.liquidity?.usd));
        const best=xs[0];
        if(!best){out.set(mint,{dexOk:false,dexReason:'NO_SOLANA_PAIR'});continue;}
        out.set(mint,{dexOk:true,dexId:best.dexId||null,pair:best.pairAddress||null,dexLiquidityUsd:n(best.liquidity?.usd),dexVolume5m:n(best.volume?.m5),dexBuys5m:n(best.txns?.m5?.buys),dexSells5m:n(best.txns?.m5?.sells)});
      }
    } catch(e) {
      for(const mint of chunk) out.set(mint,{dexOk:false,dexReason:`DEX_BATCH_TRANSIENT_${String(e?.message||e).slice(0,100)}`});
    }
  }
  return out;
}
const MAX_SELLABILITY_CHECKS_V216=8;
'''
if marker not in s:raise SystemExit('MAIN_MARKER_NOT_FOUND')
s=s.replace(marker,fn+'\n'+marker,1)
# DEX enrichment now comes from batch map, not sequential per-token calls.
needle='const final = [];\n\nfor (const item of deep) {'
replace='const final = [];\nconst dexBatchMap = await dexBatchChecks(deep);\nlet sellChecksUsedV216 = 0;\n\nfor (const item of deep) {'
if needle not in s:raise SystemExit('FINAL_LOOP_MARKER_NOT_FOUND')
s=s.replace(needle,replace,1)
pat=r'''  const dex =\n    await dexCheck\(item\.result\);'''
repl="  const dex = dexBatchMap.get(item.result.mint) || { dexOk:false, dexReason:'DEX_BATCH_MISSING' };"
s,nsub=re.subn(pat,repl,s,count=1)
if nsub!=1:raise SystemExit('DEX_CALL_PATTERN_NOT_FOUND')
# Cap expensive Jupiter reverse-route probes each cycle. Candidates beyond the
# budget remain unverified/fail-closed and are reconsidered next cycles.
old='if (opportunitySellCheck) {'
new='if (opportunitySellCheck && sellChecksUsedV216 < MAX_SELLABILITY_CHECKS_V216) {\n    sellChecksUsedV216++;'
if old not in s:raise SystemExit('SELL_CHECK_PATTERN_NOT_FOUND')
s=s.replace(old,new,1)
# Keep enough breadth for trend rotation while avoiding pointless deep work.
s=s.replace('const baseDeep = preliminary.slice(0, 30);','const baseDeep = preliminary.slice(0, 24);',1)
s=s.replace('.slice(0, 10);','.slice(0, 6);',1)
p.write_text(s)
PY
node --check "$SCANNER_DST"
grep -q 'SCANNER_FAST_PIPELINE_V216' "$SCANNER_DST"
grep -q 'dexBatchChecks' "$SCANNER_DST"
grep -q 'MAX_SELLABILITY_CHECKS_V216=8' "$SCANNER_DST"
grep -q 'preliminary.slice(0, 24)' "$SCANNER_DST"
grep -q '.slice(0, 6)' "$SCANNER_DST"
node --check "$HOLDER_STAGE"
grep -q 'HOLDER_FAST_FAIL_V215' "$HOLDER_STAGE"

install -m 0755 "$0" "$APP/ops/meme-alpha/v216-stage-fast-pipeline.sh" 2>/dev/null || true
install -m 0755 "$(cd "$(dirname "$0")" && pwd)/v216-root-apply-fast-pipeline.sh" "$APP/ops/meme-alpha/v216-root-apply-fast-pipeline.sh"

echo SCANNER_DEX_BATCH_MAX_TOKENS=30
echo SCANNER_DEEP_MAX=30
echo SCANNER_SELLABILITY_BUDGET_PER_CYCLE=8
echo JUPITER_MIN_INTERVAL_MS_PRESERVED=2200
echo JUPITER_FETCH_TIMEOUT_MS=6000
echo JUPITER_MAX_ATTEMPTS=2
echo HOLDER_FAST_FAIL_INCLUDED=TRUE
echo HOLDER_RPC_TIMEOUT_MS=2500
echo HOLDER_CONCURRENCY=4
echo HARD_SAFETY_GATES_PRESERVED=TRUE
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V216_FAST_PIPELINE_STAGE_PASS
